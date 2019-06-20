/*
 * Copyright (c) 2019 Iotic Labs Ltd. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://github.com/Iotic-Labs/py-ubjson/blob/master/LICENSE
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <Python.h>
#include <bytesobject.h>

#include "common.h"
#include "markers.h"
#include "decoder.h"
#include "python_funcs.h"

/******************************************************************************/

#define RECURSE_AND_RETURN_OR_BAIL(action, recurse_msg) {\
    PyObject *ret;\
    BAIL_ON_NONZERO(Py_EnterRecursiveCall(recurse_msg));\
    ret = (action);\
    Py_LeaveRecursiveCall();\
    return ret;\
}

#define RAISE_DECODER_EXCEPTION(msg) {\
    PyObject *num = NULL, *str = NULL, *tuple = NULL;\
    if ((num = PyLong_FromSize_t(buffer->total_read)) &&\
        (str = PyUnicode_FromString(msg)) &&\
        (tuple = PyTuple_Pack(2, str, num))) {\
        PyErr_SetObject(DecoderException, tuple);\
    /* backup method in case object creation fails */\
    } else {\
        PyErr_Format(DecoderException, "%s (at byte [%zd])", msg, buffer->total_read);\
    }\
    Py_XDECREF(tuple);\
    Py_XDECREF(num);\
    Py_XDECREF(str);\
    goto bail;\
}

// used only by READ macros below
#define ACTION_READ_ERROR(stmt, len, item_str) {\
    if (NULL == (stmt)) {\
        if (read > 0) {\
            goto bail;\
        } else if ((len > 0) || (read < len)) {\
            RAISE_DECODER_EXCEPTION(("Insufficient input (" item_str ")"));\
        }\
    } else if (read < len) {\
        RAISE_DECODER_EXCEPTION(("Insufficient (partial) input (" item_str ")"));\
    }\
}

#define READ_VIA_FUNC(buffer, readptr, dst) \
    buffer->read_func(buffer, readptr, dst)

#define READ_INTO_OR_BAIL(len, dst_buffer, item_str) {\
    Py_ssize_t read = len;\
    ACTION_READ_ERROR(READ_VIA_FUNC(buffer, &read, dst_buffer), len, item_str);\
}

#define READ_OR_BAIL(len, dst_buffer, item_str) {\
    Py_ssize_t read = len;\
    ACTION_READ_ERROR((dst_buffer = READ_VIA_FUNC(buffer, &read, NULL)), len, item_str);\
}

#define READ_OR_BAIL_CAST(len, dst_buffer, cast, item_str) {\
    Py_ssize_t read = len;\
    ACTION_READ_ERROR((dst_buffer = cast READ_VIA_FUNC(buffer, &read, NULL)), len, item_str);\
}

#define READ_CHAR_OR_BAIL(dst_char, item_str) {\
    const char* tmp;\
    READ_OR_BAIL(1, tmp, item_str);\
    dst_char = tmp[0];\
}

#define DECODE_UNICODE_OR_BAIL(dst_obj, raw, length, item_str) {\
    if (NULL == ((dst_obj) = PyUnicode_FromStringAndSize(raw, length))) {\
        RAISE_DECODER_EXCEPTION(("Failed to decode utf8: " item_str));\
    }\
}\

#define DECODE_LENGTH_OR_BAIL(length) BAIL_ON_NEGATIVE((length) = _decode_int_non_negative(buffer, NULL))

#define DECODE_LENGTH_OR_BAIL_MARKER(length, marker) \
    BAIL_ON_NEGATIVE((length) = _decode_int_non_negative(buffer, &(marker)))


// decoder buffer size when using fp (i.e. minimum number of bytes to read in one go)
#define BUFFER_FP_SIZE 256
// io.SEEK_CUR constant (for seek() function)
#define IO_SEEK_CUR 1


static PyObject *DecoderException = NULL;
static PyTypeObject *PyDec_Type = NULL;
#define PyDec_Check(v) PyObject_TypeCheck(v, PyDec_Type)

/******************************************************************************/

typedef struct {
    // next marker after container parameters
    char marker;
    // indicates whether countainer has count specified
    int counting;
    // number of elements in container (if counting or 1 if not)
    long long count;
    // type of container values, if typed, otherwise TYPE_NONE
    char type;
    // indicates the parameter specification for the container is invalid (an exception will have been set)
    int invalid;
} _container_params_t;

static const char* _decoder_buffer_read_fixed(_ubjson_decoder_buffer_t *buffer, Py_ssize_t *len, char *dst_buffer);
static const char* _decoder_buffer_read_callable(_ubjson_decoder_buffer_t *buffer, Py_ssize_t *len, char *dst_buffer);
static const char* _decoder_buffer_read_buffered(_ubjson_decoder_buffer_t *buffer, Py_ssize_t *len, char *dst_buffer);

//These functions return NULL on failure (an exception will have been set). Note that no type checking is performed!

static PyObject* _decode_int8(_ubjson_decoder_buffer_t *buffer);
static PyObject* _decode_int16_32(_ubjson_decoder_buffer_t *buffer, Py_ssize_t size);
static PyObject* _decode_int64(_ubjson_decoder_buffer_t *buffer);
static PyObject* _decode_float32(_ubjson_decoder_buffer_t *buffer);
static PyObject* _decode_float64(_ubjson_decoder_buffer_t *buffer);
static PyObject* _decode_high_prec(_ubjson_decoder_buffer_t *buffer);
static long long _decode_int_non_negative(_ubjson_decoder_buffer_t *buffer, char *given_marker);
static PyObject* _decode_char(_ubjson_decoder_buffer_t *buffer);
static PyObject* _decode_string(_ubjson_decoder_buffer_t *buffer);
static _container_params_t _get_container_params(_ubjson_decoder_buffer_t *buffer, int in_mapping);
static int _is_no_data_type(char type);
static PyObject* _no_data_type(char type);
static PyObject* _decode_array(_ubjson_decoder_buffer_t *buffer);
static PyObject* _decode_object_with_pairs_hook(_ubjson_decoder_buffer_t *buffer);
static PyObject* _decode_object(_ubjson_decoder_buffer_t *buffer);

/******************************************************************************/

/* Returns new decoder buffer or NULL on failure (an exception will be set). Input must either support buffer interface
 * or be callable. Currently only increases reference count for input parameter.
 */
_ubjson_decoder_buffer_t* _ubjson_decoder_buffer_create(_ubjson_decoder_prefs_t* prefs, PyObject *input,
                                                        PyObject *seek) {
    _ubjson_decoder_buffer_t *buffer;

    if (NULL == (buffer = calloc(1, sizeof(_ubjson_decoder_buffer_t)))) {
        PyErr_NoMemory();
        return NULL;
    }

    buffer->prefs = *prefs;
    buffer->input = input;
    Py_XINCREF(input);

    if (PyObject_CheckBuffer(input)) {
        BAIL_ON_NONZERO(PyObject_GetBuffer(input, &buffer->view, PyBUF_SIMPLE));
        buffer->read_func = _decoder_buffer_read_fixed;
        buffer->view_set = 1;
    } else if (PyCallable_Check(input)) {
        if (NULL == seek) {
            buffer->read_func = _decoder_buffer_read_callable;
        } else {
            buffer->read_func = _decoder_buffer_read_buffered;
            buffer->seek = seek;
            Py_INCREF(seek);
        }
    } else {
        // Should have been checked a level above
        PyErr_SetString(PyExc_TypeError, "Input neither support buffer interface nor is callable");
        goto bail;
    }
    // treat Py_None as no argument being supplied
    if (Py_None == buffer->prefs.object_hook) {
        buffer->prefs.object_hook = NULL;
    }
    if (Py_None == buffer->prefs.object_pairs_hook) {
        buffer->prefs.object_pairs_hook = NULL;
    }

    return buffer;

bail:
    _ubjson_decoder_buffer_free(&buffer);
    return NULL;
}

// Returns non-zero if buffer cleanup/finalisation failed and no other exception was set already
int _ubjson_decoder_buffer_free(_ubjson_decoder_buffer_t **buffer) {
    int failed = 0;

    if (NULL != buffer && NULL != *buffer) {
        if ((*buffer)->view_set) {
            // In buffered mode, rewind to position in stream up to which actually read (rather than buffered)
            if (NULL != (*buffer)->seek && (*buffer)->view.len > (*buffer)->pos) {
                PyObject *type, *value, *traceback, *seek_result;

                // preserve the previous exception, if set
                PyErr_Fetch(&type, &value, &traceback);

                seek_result = PyObject_CallFunction((*buffer)->seek, "nn", ((*buffer)->pos - (*buffer)->view.len),
                                                    IO_SEEK_CUR);
                Py_XDECREF(seek_result);

                /* Blindly calling PyErr_Restore would clear any exception raised by seek call. If however already had
                 * an error before freeing buffer (this function), propagate that instead. (I.e. this behaves like a
                 * nested try-except block.
                 */
                if (NULL != type) {
                    PyErr_Restore(type, value, traceback);
                } else if (NULL == seek_result) {
                    failed = 1;
                }
            }
            PyBuffer_Release(&((*buffer)->view));
            (*buffer)->view_set = 0;
        }
        if (NULL != (*buffer)->tmp_dst) {
            free((*buffer)->tmp_dst);
            (*buffer)->tmp_dst = NULL;
        }
        Py_CLEAR((*buffer)->input);
        Py_CLEAR((*buffer)->seek);
        free(*buffer);
        *buffer = NULL;
    }
    return failed;
}

/* Tries to read len bytes from input, returning read chunk. Len is updated to how many bytes were actually read.
 * If not NULL, dst_buffer can be an existing buffer to output len bytes into.
 * Returns NULL if either no input is left (len is set to zero) or an error occurs (len is non-zero). The caller must
 * NOT modify or free the returned chunk unless they specified out_buffer (in which case that is returned). When this
 * function is called again, the previously returned output is no longer valid (unless was created by caller).
 *
 * This function reads from a fixed buffer (single byte array)
 */
static const char* _decoder_buffer_read_fixed(_ubjson_decoder_buffer_t *buffer, Py_ssize_t *len, char *dst_buffer) {
    Py_ssize_t old_pos;

    if (0 == *len) {
        return NULL;
    }

    if (buffer->total_read < buffer->view.len) {
        *len = MIN(*len, (buffer->view.len - buffer->total_read));
        old_pos = buffer->total_read;
        buffer->total_read += *len;
        // caller has provided own destination
        if (NULL != dst_buffer) {
            return memcpy(dst_buffer, &((char*)buffer->view.buf)[old_pos], *len);
        } else {
            return &((char*)buffer->view.buf)[old_pos];
        }
    // no input remaining
    } else {
        *len = 0;
        return NULL;
    }
}

// See _decoder_buffer_read_fixed for behaviour details. This function is used to read from a stream
static const char* _decoder_buffer_read_callable(_ubjson_decoder_buffer_t *buffer, Py_ssize_t *len, char *dst_buffer) {
    PyObject* read_result = NULL;

    if (0 == *len) {
        return NULL;
    }

    if (buffer->view_set) {
        PyBuffer_Release(&buffer->view);
        buffer->view_set = 0;
    }

    // read input and get buffer view
    BAIL_ON_NULL(read_result = PyObject_CallFunction(buffer->input, "n", *len));
    BAIL_ON_NONZERO(PyObject_GetBuffer(read_result, &buffer->view, PyBUF_SIMPLE));
    buffer->view_set = 1;
    // don't need reference since view reserves one already
    Py_CLEAR(read_result);

    // no input remaining
    if (0 == buffer->view.len) {
        *len = 0;
        return NULL;
    }

    *len = buffer->view.len;
    buffer->total_read += *len;
    // caller has provided own destination
    if (NULL != dst_buffer) {
        return memcpy(dst_buffer, buffer->view.buf, *len);
    } else {
        return buffer->view.buf;
    }

bail:
    *len = 1;
    Py_XDECREF(read_result);
    return NULL;
}

// See _decoder_buffer_read_fixed for behaviour details. This function reads (buffered) from a seekable stream
static const char* _decoder_buffer_read_buffered(_ubjson_decoder_buffer_t *buffer, Py_ssize_t *len, char *dst_buffer) {
    Py_ssize_t old_pos;
    char *tmp_dst;
    Py_ssize_t remaining_old = 0; // how many bytes remaining to be read (from old view)
    PyObject* read_result = NULL;

    if (0 == *len) {
        return NULL;
    }

    // previously used temporary output no longer needed
    if (NULL != buffer->tmp_dst) {
        free(buffer->tmp_dst);
        buffer->tmp_dst = NULL;
    }
    // will require additional read if remaining input smaller than requested
    if (!buffer->view_set || *len > (buffer->view.len - buffer->pos)) {
        // create temporary buffer if not supplied (and have some remaining input in view)
        if (NULL == dst_buffer) {
            if (NULL == (tmp_dst = buffer->tmp_dst = malloc(sizeof(char) * (size_t)*len))) {
                PyErr_NoMemory();
                goto bail;
            }
        } else {
            tmp_dst = dst_buffer;
        }

        // copy remainder into buffer and release old view
        if (buffer->view_set) {
            remaining_old = buffer->view.len - buffer->pos;
            if (remaining_old > 0) {
                memcpy(tmp_dst, &((char*)buffer->view.buf)[buffer->pos], remaining_old);
                buffer->pos = buffer->view.len;
                buffer->total_read += remaining_old;
            }
            PyBuffer_Release(&buffer->view);
            buffer->view_set = 0;
            buffer->pos = 0;
        }

        // read input and get buffer view
        BAIL_ON_NULL(read_result = PyObject_CallFunction(buffer->input, "n",
                                                         MAX(BUFFER_FP_SIZE, (*len - remaining_old))));
        BAIL_ON_NONZERO(PyObject_GetBuffer(read_result, &buffer->view, PyBUF_SIMPLE));
        buffer->view_set = 1;
        // don't need reference since view reserves one already
        Py_CLEAR(read_result);

        // no input remaining
        if (0 == remaining_old && buffer->view.len == 0) {
            *len = 0;
            return NULL;
        }

        // read rest into buffer (adjusting total length if not all available)
        *len = MIN(*len, (buffer->view.len - buffer->pos) + remaining_old);
        buffer->pos = *len - remaining_old;
        buffer->total_read += buffer->pos;
        memcpy(&tmp_dst[remaining_old], (char*)buffer->view.buf, buffer->pos);
        return tmp_dst;

    // enough data in existing view
    } else {
        old_pos = buffer->pos;
        buffer->pos += *len;
        buffer->total_read += *len;
        // caller has provided own destination
        if (NULL != dst_buffer) {
            return memcpy(dst_buffer, &((char*)buffer->view.buf)[old_pos], *len);
        } else {
            return &((char*)buffer->view.buf)[old_pos];
        }
    }

bail:
    *len = 1;
    Py_XDECREF(read_result);
    return NULL;
}


/******************************************************************************/

// These methods are partially based on Python's _struct.c

static PyObject* _decode_int8(_ubjson_decoder_buffer_t *buffer) {
    char value;

    READ_CHAR_OR_BAIL(value, "int8");
#if PY_MAJOR_VERSION < 3
    return PyInt_FromLong((long) (signed char)value);
#else
    return PyLong_FromLong((long) (signed char)value);
#endif

bail:
    return NULL;
}

static PyObject* _decode_uint8(_ubjson_decoder_buffer_t *buffer) {
    char value;

    READ_CHAR_OR_BAIL(value, "uint8");
#if PY_MAJOR_VERSION < 3
    return PyInt_FromLong((long) (unsigned char)value);
#else
    return PyLong_FromLong((long) (unsigned char)value);
#endif

bail:
    return NULL;
}

// NOTE: size parameter can only be 2 or 4 (bytes)
static PyObject* _decode_int16_32(_ubjson_decoder_buffer_t *buffer, Py_ssize_t size) {
    const unsigned char *raw;
    long value = 0;
    Py_ssize_t i;

    READ_OR_BAIL_CAST(size, raw, (const unsigned char *), "int16/32");

    for (i = size; i > 0; i--) {
        value = (value << 8) | *raw++;
    }
    // extend signed bit
    if (SIZEOF_LONG > size) {
        value |= -(value & (1L << ((8 * size) - 1)));
    }
#if PY_MAJOR_VERSION < 3
    return PyInt_FromLong(value);
#else
    return PyLong_FromLong(value);
#endif

bail:
    return NULL;
}

static PyObject* _decode_int64(_ubjson_decoder_buffer_t *buffer) {
    const unsigned char *raw;
    long long value = 0;
    const Py_ssize_t size = 8;
    Py_ssize_t i;

    READ_OR_BAIL_CAST(8, raw, (const unsigned char *), "int64");

    for (i = size; i > 0; i--) {
        value = (value << 8) | *raw++;
    }
    // extend signed bit
    if (SIZEOF_LONG_LONG > 8) {
        value |= -(value & ((long long)1 << ((8 * size) - 1)));
    }
    if (value >= LONG_MIN && value <= LONG_MAX) {
        return PyLong_FromLong(Py_SAFE_DOWNCAST(value, long long, long));
    } else {
        return PyLong_FromLongLong(value);
    }

bail:
    return NULL;
}

// returns negative on error (exception set)
static long long _decode_int_non_negative(_ubjson_decoder_buffer_t *buffer, char *given_marker) {
    char marker;
    PyObject *int_obj = NULL;
    long long value;

    if (NULL == given_marker) {
        READ_CHAR_OR_BAIL(marker, "Length marker");
    } else {
        marker = *given_marker;
    }

    switch (marker) {
        case TYPE_INT8:
            BAIL_ON_NULL(int_obj = _decode_int8(buffer));
            break;
        case TYPE_UINT8:
            BAIL_ON_NULL(int_obj = _decode_uint8(buffer));
            break;
        case TYPE_INT16:
            BAIL_ON_NULL(int_obj = _decode_int16_32(buffer, 2));
            break;
        case TYPE_INT32:
            BAIL_ON_NULL(int_obj = _decode_int16_32(buffer, 4));
            break;
        case TYPE_INT64:
            BAIL_ON_NULL(int_obj = _decode_int64(buffer));
            break;
        default:
            RAISE_DECODER_EXCEPTION("Integer marker expected");
    }
#if PY_MAJOR_VERSION < 3
    if (PyInt_Check(int_obj)) {
        value = PyInt_AsLong(int_obj);
    } else
#endif
    {
        // not expecting this to occur unless LONG_MAX (sys.maxint in Python 2) < 2^63-1
        value = PyLong_AsLongLong(int_obj);
    }
    if (PyErr_Occurred()) {
        goto bail;
    }
    if (value < 0) {
        RAISE_DECODER_EXCEPTION("Negative count/length unexpected");
    }
    Py_XDECREF(int_obj);

    return value;

bail:
    Py_XDECREF(int_obj);
    return -1;
}

static PyObject* _decode_float32(_ubjson_decoder_buffer_t *buffer) {
    const char *raw;
    double value;

    READ_OR_BAIL(4, raw, "float32");
    value = _pyfuncs_ubj_PyFloat_Unpack4((const unsigned char *)raw, 0);
    if ((-1.0 == value) && PyErr_Occurred()) {
        goto bail;
    }
    return PyFloat_FromDouble(value);

bail:
    return NULL;
}

static PyObject* _decode_float64(_ubjson_decoder_buffer_t *buffer) {
    const char *raw;
    double value;

    READ_OR_BAIL(8, raw, "float64");
    value = _pyfuncs_ubj_PyFloat_Unpack8((const unsigned char *)raw, 0);
    if ((-1.0 == value) && PyErr_Occurred()) {
        goto bail;
    }
    return PyFloat_FromDouble(value);

bail:
    return NULL;
}

static PyObject* _decode_high_prec(_ubjson_decoder_buffer_t *buffer) {
    const char *raw;
    PyObject *num_str = NULL;
    PyObject *decimal;
    long long length;

    DECODE_LENGTH_OR_BAIL(length);
    READ_OR_BAIL((Py_ssize_t)length, raw, "highprec");

    DECODE_UNICODE_OR_BAIL(num_str, raw, (Py_ssize_t)length, "highprec");

    BAIL_ON_NULL(decimal = PyObject_CallFunctionObjArgs((PyObject*)PyDec_Type, num_str, NULL));
    Py_XDECREF(num_str);
    return decimal;

bail:
    Py_XDECREF(num_str);
    return NULL;
}

static PyObject* _decode_char(_ubjson_decoder_buffer_t *buffer) {
    char value;
    PyObject *obj = NULL;

    READ_CHAR_OR_BAIL(value, "char");
    DECODE_UNICODE_OR_BAIL(obj, &value, 1, "char");
    return obj;

bail:
    Py_XDECREF(obj);
    return NULL;
}

static PyObject* _decode_string(_ubjson_decoder_buffer_t *buffer) {
    long long length;
    const char *raw;
    PyObject *obj = NULL;

    DECODE_LENGTH_OR_BAIL(length);

    if (length > 0) {
        READ_OR_BAIL((Py_ssize_t)length, raw, "string");
        DECODE_UNICODE_OR_BAIL(obj, raw, (Py_ssize_t)length, "string");
    } else {
        BAIL_ON_NULL(obj = PyUnicode_FromStringAndSize(NULL, 0));
    }
    return obj;

bail:
    Py_XDECREF(obj);
    return NULL;
}

static _container_params_t _get_container_params(_ubjson_decoder_buffer_t *buffer, int in_mapping) {
    _container_params_t params;
    char marker;

    // fixed type for all values
    READ_CHAR_OR_BAIL(marker, "container type, count or 1st key/value type");
    if (CONTAINER_TYPE == marker) {
        READ_CHAR_OR_BAIL(marker, "container type");
        switch (marker) {
            case TYPE_NULL: case TYPE_BOOL_TRUE: case TYPE_BOOL_FALSE: case TYPE_CHAR: case TYPE_STRING: case TYPE_INT8:
            case TYPE_UINT8: case TYPE_INT16: case TYPE_INT32: case TYPE_INT64: case TYPE_FLOAT32: case TYPE_FLOAT64:
            case TYPE_HIGH_PREC: case ARRAY_START: case OBJECT_START:
                params.type = marker;
                break;
            default:
                RAISE_DECODER_EXCEPTION("Invalid container type");
        }
        READ_CHAR_OR_BAIL(marker, "container count or 1st key/value type");
    } else {
        // container type not fixed
        params.type = TYPE_NONE;
    }

    // container value count
    if (CONTAINER_COUNT == marker) {
        params.counting = 1;
        DECODE_LENGTH_OR_BAIL(params.count);
        // reading ahead just to capture type, which will not exist if type is fixed
        if ((params.count > 0) && (in_mapping || (TYPE_NONE == params.type))) {
            READ_CHAR_OR_BAIL(marker, "1st key/value type");
        } else {
            marker = params.type;
        }
    } else if (TYPE_NONE == params.type) {
        // count not provided but indicate that
        params.count = 1;
        params.counting = 0;
    } else {
        RAISE_DECODER_EXCEPTION("Container type without count");
    }

    params.marker = marker;
    params.invalid = 0;
    return params;

bail:
    params.invalid = 1;
    return params;
}

static int _is_no_data_type(char type) {
    return ((TYPE_NULL == type) || (TYPE_BOOL_TRUE == type) || (TYPE_BOOL_FALSE == type));
}

// Note: Does NOT reserve a new reference
static PyObject* _no_data_type(char type) {
    switch (type) {
        case TYPE_NULL:
            return Py_None;
        case TYPE_BOOL_TRUE:
            return Py_True;
        case TYPE_BOOL_FALSE:
            return Py_False;
        default:
            PyErr_SetString(PyExc_RuntimeError, "Internal error - _no_data_type");
            return NULL;
    }
}

static PyObject* _decode_array(_ubjson_decoder_buffer_t *buffer) {
    _container_params_t params = _get_container_params(buffer, 0);
    PyObject *list = NULL;
    PyObject *value = NULL;
    char marker;

    if (params.invalid) {
        goto bail;
    }
    marker = params.marker;

    if (params.counting) {
        // special case - byte array
        if ((TYPE_UINT8 == params.type) && !buffer->prefs.no_bytes) {
            BAIL_ON_NULL(list = PyBytes_FromStringAndSize(NULL, params.count));
            READ_INTO_OR_BAIL(params.count, PyBytes_AS_STRING(list), "bytes array");
            return list;
        // special case - no data types
        } else if (_is_no_data_type(params.type)) {
            BAIL_ON_NULL(list = PyList_New(params.count));
            BAIL_ON_NULL(value = _no_data_type(params.type));

            while (params.count > 0) {
                PyList_SET_ITEM(list, --params.count, value);
                // reference stolen each time
                Py_INCREF(value);
            }
            value = NULL;
        // take advantage of faster creation/setting of list since count known
        } else {
            Py_ssize_t list_pos = 0; // position in list for far fast setting via PyList_SET_ITEM

            BAIL_ON_NULL(list = PyList_New(params.count));

            while (params.count > 0) {
                if (TYPE_NOOP == marker) {
                    READ_CHAR_OR_BAIL(marker, "array value type marker (sized, after no-op)");
                    continue;
                }
                BAIL_ON_NULL(value = _ubjson_decode_value(buffer, &marker));
                PyList_SET_ITEM(list, list_pos++, value);
                // reference stolen by list so no longer want to decrement on failure
                value = NULL;
                params.count--;
                if (params.count > 0 && TYPE_NONE == params.type) {
                    READ_CHAR_OR_BAIL(marker, "array value type marker (sized)");
                }
            }
        }
    } else {
        BAIL_ON_NULL(list = PyList_New(0));

        while (ARRAY_END != marker) {
            if (TYPE_NOOP == marker) {
                READ_CHAR_OR_BAIL(marker, "array value type marker (after no-op)");
                continue;
            }
            BAIL_ON_NULL(value = _ubjson_decode_value(buffer, &marker));
            BAIL_ON_NONZERO(PyList_Append(list, value));
            Py_CLEAR(value);

            if (TYPE_NONE == params.type) {
                READ_CHAR_OR_BAIL(marker, "array value type marker");
            }
        }
    }

    return list;

bail:
    Py_XDECREF(value);
    Py_XDECREF(list);
    return NULL;
}

// same as string, except there is no 'S' marker
static PyObject* _decode_object_key(_ubjson_decoder_buffer_t *buffer, char marker, int intern) {
    long long length;
    const char *raw;
    PyObject *key;

    DECODE_LENGTH_OR_BAIL_MARKER(length, marker);
    READ_OR_BAIL((Py_ssize_t)length, raw, "string");

    BAIL_ON_NULL(key = PyUnicode_FromStringAndSize(raw, (Py_ssize_t)length));
// unicode string interning not supported in v2
#if PY_MAJOR_VERSION < 3
    UNUSED(intern);
#else
    if (intern) {
        PyUnicode_InternInPlace(&key);
    }
#endif
    return key;

bail:
    return NULL;
}

// used by _decode_object* functions
#define DECODE_OBJECT_KEY_OR_RAISE_ENCODER_EXCEPTION(context_str, intern) {\
    key = _decode_object_key(buffer, marker, intern);\
    if (NULL == key) {\
        RAISE_DECODER_EXCEPTION("Failed to decode object key (" context_str ")");\
    }\
}

static PyObject* _decode_object_with_pairs_hook(_ubjson_decoder_buffer_t *buffer) {
    _container_params_t params = _get_container_params(buffer, 1);
    PyObject *obj = NULL;
    PyObject *list = NULL;
    PyObject *key = NULL;
    PyObject *value = NULL;
    PyObject *item = NULL;
    char *fixed_type;
    char marker;
    int intern = buffer->prefs.intern_object_keys;

    if (params.invalid) {
        goto bail;
    }
    marker = params.marker;

    // take advantage of faster creation/setting of list since count known
    if (params.counting) {
        Py_ssize_t list_pos = 0; // position in list for far fast setting via PyList_SET_ITEM

        BAIL_ON_NULL(list = PyList_New(params.count));

        // special case: no data values (keys only)
        if (_is_no_data_type(params.type)) {
            value = _no_data_type(params.type);
            Py_INCREF(value);

            while (params.count > 0) {
                DECODE_OBJECT_KEY_OR_RAISE_ENCODER_EXCEPTION("sized, no data", intern);
                BAIL_ON_NULL(item = PyTuple_Pack(2, key, value));
                Py_CLEAR(key);
                PyList_SET_ITEM(list, list_pos++, item);
                // reference stolen
                item = NULL;

                params.count--;
                if (params.count > 0) {
                    READ_CHAR_OR_BAIL(marker, "object key length");
                }
            }
        } else {
            fixed_type = (TYPE_NONE == params.type) ? NULL : &params.type;

            while (params.count > 0) {
                if (TYPE_NOOP == marker) {
                    READ_CHAR_OR_BAIL(marker, "object key length (sized, after no-op)");
                    continue;
                }
                DECODE_OBJECT_KEY_OR_RAISE_ENCODER_EXCEPTION("sized", intern);
                BAIL_ON_NULL(value = _ubjson_decode_value(buffer, fixed_type));
                BAIL_ON_NULL(item = PyTuple_Pack(2, key, value));
                Py_CLEAR(key);
                Py_CLEAR(value);
                PyList_SET_ITEM(list, list_pos++, item);
                // reference stolen
                item = NULL;

                params.count--;
                if (params.count > 0) {
                    READ_CHAR_OR_BAIL(marker, "object key length (sized)");
                }
            }
        }
    } else {
        BAIL_ON_NULL(list = PyList_New(0));
        fixed_type = (TYPE_NONE == params.type) ? NULL : &params.type;

        while (OBJECT_END != marker) {
            if (TYPE_NOOP == marker) {
                READ_CHAR_OR_BAIL(marker, "object key length (after no-op)");
                continue;
            }
            DECODE_OBJECT_KEY_OR_RAISE_ENCODER_EXCEPTION("unsized", intern);
            BAIL_ON_NULL(value = _ubjson_decode_value(buffer, fixed_type));
            BAIL_ON_NULL(item = PyTuple_Pack(2, key, value));
            Py_CLEAR(key);
            Py_CLEAR(value);
            BAIL_ON_NONZERO(PyList_Append(list, item));
            Py_CLEAR(item);

            READ_CHAR_OR_BAIL(marker, "object key length");
        }
    }

    BAIL_ON_NULL(obj = PyObject_CallFunctionObjArgs(buffer->prefs.object_pairs_hook, list, NULL));
    Py_XDECREF(list);
    return obj;

bail:
    Py_XDECREF(obj);
    Py_XDECREF(list);
    Py_XDECREF(key);
    Py_XDECREF(value);
    Py_XDECREF(item);
    return NULL;
}

static PyObject* _decode_object(_ubjson_decoder_buffer_t *buffer) {
    _container_params_t params = _get_container_params(buffer, 1);
    PyObject *obj = NULL;
    PyObject *newobj = NULL; // result of object_hook (if applicable)
    PyObject *key = NULL;
    PyObject *value = NULL;
    char *fixed_type;
    char marker;
    int intern = buffer->prefs.intern_object_keys;

    if (params.invalid) {
        goto bail;
    }
    marker = params.marker;

    BAIL_ON_NULL(obj = PyDict_New());

    // special case: no data values (keys only)
    if (params.counting && _is_no_data_type(params.type)) {
        value = _no_data_type(params.type);

        while (params.count > 0) {
            DECODE_OBJECT_KEY_OR_RAISE_ENCODER_EXCEPTION("sized, no data", intern);
            BAIL_ON_NONZERO(PyDict_SetItem(obj, key, value));
            // reference stolen in above call, but only for value!
            Py_CLEAR(key);
            Py_INCREF(value);

            params.count--;
            if (params.count > 0) {
                READ_CHAR_OR_BAIL(marker, "object key length");
            }
        }
    } else {
        fixed_type = (TYPE_NONE == params.type) ? NULL : &params.type;

        while (params.count > 0 && (params.counting || (OBJECT_END != marker))) {
            if (TYPE_NOOP == marker) {
                READ_CHAR_OR_BAIL(marker, "object key length");
                continue;
            }
            DECODE_OBJECT_KEY_OR_RAISE_ENCODER_EXCEPTION("sized/unsized", intern);
            BAIL_ON_NULL(value = _ubjson_decode_value(buffer, fixed_type));
            BAIL_ON_NONZERO(PyDict_SetItem(obj, key, value));
            Py_CLEAR(key);
            Py_CLEAR(value);

            if (params.counting) {
                params.count--;
            }
            if (params.count > 0) {
                READ_CHAR_OR_BAIL(marker, "object key length");
            }
        }
    }

    if (NULL != buffer->prefs.object_hook) {
        BAIL_ON_NULL(newobj = PyObject_CallFunctionObjArgs(buffer->prefs.object_hook, obj, NULL));
        Py_CLEAR(obj);
        return newobj;
    }
    return obj;

bail:
    Py_XDECREF(key);
    Py_XDECREF(value);
    Py_XDECREF(obj);
    Py_XDECREF(newobj);
    return NULL;
}

/******************************************************************************/

// only used by _ubjson_decode_value
#define RETURN_OR_RAISE_DECODER_EXCEPTION(item, item_str) {\
    obj = (item);\
    if (NULL != obj) {\
        return obj;\
    } else if (PyErr_Occurred() && PyErr_ExceptionMatches((PyObject*)DecoderException)) {\
        goto bail;\
    } else {\
        RAISE_DECODER_EXCEPTION("Failed to decode " item_str);\
    }\
}

PyObject* _ubjson_decode_value(_ubjson_decoder_buffer_t *buffer, char *given_marker) {
    char marker;
    PyObject *obj;

    if (NULL == given_marker) {
        READ_CHAR_OR_BAIL(marker, "Type marker");
    } else {
        marker = *given_marker;
    }

    switch (marker) {
        case TYPE_NULL:
            Py_RETURN_NONE;
        case TYPE_BOOL_TRUE:
            Py_RETURN_TRUE;
        case TYPE_BOOL_FALSE:
            Py_RETURN_FALSE;
        case TYPE_CHAR:
            RETURN_OR_RAISE_DECODER_EXCEPTION(_decode_char(buffer), "char");
        case TYPE_STRING:
            RETURN_OR_RAISE_DECODER_EXCEPTION(_decode_string(buffer), "string");
        case TYPE_INT8:
            RETURN_OR_RAISE_DECODER_EXCEPTION(_decode_int8(buffer), "int8");
        case TYPE_UINT8:
            RETURN_OR_RAISE_DECODER_EXCEPTION(_decode_uint8(buffer), "uint8");
        case TYPE_INT16:
            RETURN_OR_RAISE_DECODER_EXCEPTION(_decode_int16_32(buffer, 2), "int16");
        case TYPE_INT32:
            RETURN_OR_RAISE_DECODER_EXCEPTION(_decode_int16_32(buffer, 4), "int32");
        case TYPE_INT64:
            RETURN_OR_RAISE_DECODER_EXCEPTION(_decode_int64(buffer), "int64");
        case TYPE_FLOAT32:
            RETURN_OR_RAISE_DECODER_EXCEPTION(_decode_float32(buffer), "float32");
        case TYPE_FLOAT64:
            RETURN_OR_RAISE_DECODER_EXCEPTION(_decode_float64(buffer), "float64");
        case TYPE_HIGH_PREC:
            RETURN_OR_RAISE_DECODER_EXCEPTION(_decode_high_prec(buffer), "highprec");
        case ARRAY_START:
            RECURSE_AND_RETURN_OR_BAIL(_decode_array(buffer), "whilst decoding a UBJSON array");
        case OBJECT_START:
            if (NULL == buffer->prefs.object_pairs_hook) {
                RECURSE_AND_RETURN_OR_BAIL(_decode_object(buffer), "whilst decoding a UBJSON object");
            } else {
                RECURSE_AND_RETURN_OR_BAIL(_decode_object_with_pairs_hook(buffer), "whilst decoding a UBJSON object");
            }
        default:
            RAISE_DECODER_EXCEPTION("Invalid marker");
    }

bail:
    return NULL;
}

/******************************************************************************/

int _ubjson_decoder_init(void) {
    PyObject *tmp_module = NULL;
    PyObject *tmp_obj = NULL;

    // try to determine floating point format / endianess
    _pyfuncs_ubj_detect_formats();

    // allow decoder to access DecoderException & Decimal class
    BAIL_ON_NULL(tmp_module = PyImport_ImportModule("ubjson.decoder"));
    BAIL_ON_NULL(DecoderException = PyObject_GetAttrString(tmp_module, "DecoderException"));
    Py_CLEAR(tmp_module);

    BAIL_ON_NULL(tmp_module = PyImport_ImportModule("decimal"));
    BAIL_ON_NULL(tmp_obj = PyObject_GetAttrString(tmp_module, "Decimal"));
    if (!PyType_Check(tmp_obj)) {
        PyErr_SetString(PyExc_ImportError, "decimal.Decimal type import failure");
        goto bail;
    }
    PyDec_Type = (PyTypeObject*) tmp_obj;
    Py_CLEAR(tmp_module);

    return 0;

bail:
    Py_CLEAR(DecoderException);
    Py_CLEAR(PyDec_Type);
    Py_XDECREF(tmp_obj);
    Py_XDECREF(tmp_module);
    return 1;
}


void _ubjson_decoder_cleanup(void) {
    Py_CLEAR(DecoderException);
    Py_CLEAR(PyDec_Type);
}
