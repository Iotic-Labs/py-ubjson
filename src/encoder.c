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
#include "encoder.h"
#include "python_funcs.h"

/******************************************************************************/

static char bytes_array_prefix[] = {ARRAY_START, CONTAINER_TYPE, TYPE_UINT8, CONTAINER_COUNT};

#define POWER_TWO(x) ((long long) 1 << (x))

#if defined(_MSC_VER) && !defined(fpclassify)
#   define USE__FPCLASS
#endif

// initial encoder buffer size (when not supplied with fp)
#define BUFFER_INITIAL_SIZE 64
// encoder buffer size when using fp (i.e. minimum number of bytes to buffer before writing out)
#define BUFFER_FP_SIZE 256

static PyObject *EncoderException = NULL;
static PyTypeObject *PyDec_Type = NULL;
#define PyDec_Check(v) PyObject_TypeCheck(v, PyDec_Type)

/******************************************************************************/

static int _encoder_buffer_write(_ubjson_encoder_buffer_t *buffer, const char* const chunk, size_t chunk_len);

#define RECURSE_AND_BAIL_ON_NONZERO(action, recurse_msg) {\
    int ret;\
    BAIL_ON_NONZERO(Py_EnterRecursiveCall(recurse_msg));\
    ret = (action);\
    Py_LeaveRecursiveCall();\
    BAIL_ON_NONZERO(ret);\
}

#define WRITE_OR_BAIL(str, len) BAIL_ON_NONZERO(_encoder_buffer_write(buffer, (str), len))
#define WRITE_CHAR_OR_BAIL(c) {\
    char ctmp = (c);\
    WRITE_OR_BAIL(&ctmp, 1);\
}

/* These functions return non-zero on failure (an exception will have been set). Note that no type checking is performed
 * where a Python type is mentioned in the function name!
 */
static int _encode_PyBytes(PyObject *obj, _ubjson_encoder_buffer_t *buffer);
static int _encode_PyObject_as_PyDecimal(PyObject *obj, _ubjson_encoder_buffer_t *buffer);
static int _encode_PyDecimal(PyObject *obj, _ubjson_encoder_buffer_t *buffer);
static int _encode_PyUnicode(PyObject *obj, _ubjson_encoder_buffer_t *buffer);
static int _encode_PyFloat(PyObject *obj, _ubjson_encoder_buffer_t *buffer);
static int _encode_PyLong(PyObject *obj, _ubjson_encoder_buffer_t *buffer);
static int _encode_longlong(long long num, _ubjson_encoder_buffer_t *buffer);
#if PY_MAJOR_VERSION < 3
static int _encode_PyInt(PyObject *obj, _ubjson_encoder_buffer_t *buffer);
#endif
static int _encode_PySequence(PyObject *obj, _ubjson_encoder_buffer_t *buffer);
static int _encode_mapping_key(PyObject *obj, _ubjson_encoder_buffer_t *buffer);
static int _encode_PyMapping(PyObject *obj, _ubjson_encoder_buffer_t *buffer);

/******************************************************************************/

/* fp_write, if not NULL, must be a callable which accepts a single bytes argument. On failure will set exception.
 * Currently only increases reference count for fp_write parameter.
 */
_ubjson_encoder_buffer_t* _ubjson_encoder_buffer_create(_ubjson_encoder_prefs_t* prefs, PyObject *fp_write) {
    _ubjson_encoder_buffer_t *buffer;

    if (NULL == (buffer = calloc(1, sizeof(_ubjson_encoder_buffer_t)))) {
        PyErr_NoMemory();
        return NULL;
    }

    buffer->len = (NULL != fp_write) ? BUFFER_FP_SIZE : BUFFER_INITIAL_SIZE;
    BAIL_ON_NULL(buffer->obj = PyBytes_FromStringAndSize(NULL, buffer->len));
    buffer->raw = PyBytes_AS_STRING(buffer->obj);
    buffer->pos = 0;

    BAIL_ON_NULL(buffer->markers = PySet_New(NULL));

    buffer->prefs = *prefs;
    buffer->fp_write = fp_write;
    Py_XINCREF(fp_write);

    // treat Py_None as no default_func being supplied
    if (Py_None == buffer->prefs.default_func) {
        buffer->prefs.default_func = NULL;
    }

    return buffer;

bail:
    _ubjson_encoder_buffer_free(&buffer);
    return NULL;
}

void _ubjson_encoder_buffer_free(_ubjson_encoder_buffer_t **buffer) {
    if (NULL != buffer && NULL != *buffer) {
        Py_XDECREF((*buffer)->obj);
        Py_XDECREF((*buffer)->fp_write);
        Py_XDECREF((*buffer)->markers);
        free(*buffer);
        *buffer = NULL;
    }
}

// Note: Sets python exception on failure and returns non-zero
static int _encoder_buffer_write(_ubjson_encoder_buffer_t *buffer, const char* const chunk, size_t chunk_len) {
    size_t new_len;
    PyObject *fp_write_ret;

    if (0 == chunk_len) {
        return 0;
    }

    // no write method, use buffer only
    if (NULL == buffer->fp_write) {
        // increase buffer size if too small
        if (chunk_len > (buffer->len - buffer->pos)) {
            for (new_len = buffer->len; new_len < (buffer->pos + chunk_len); new_len *= 2);
            BAIL_ON_NONZERO(_PyBytes_Resize(&buffer->obj, new_len));
            buffer->raw = PyBytes_AS_STRING(buffer->obj);
            buffer->len = new_len;
        }
        memcpy(&(buffer->raw[buffer->pos]), chunk, sizeof(char) * chunk_len);
        buffer->pos += chunk_len;

    } else {
        // increase buffer to fit all first
        if (chunk_len > (buffer->len - buffer->pos)) {
            BAIL_ON_NONZERO(_PyBytes_Resize(&buffer->obj, (buffer->pos + chunk_len)));
            buffer->raw = PyBytes_AS_STRING(buffer->obj);
            buffer->len = buffer->pos + chunk_len;
        }
        memcpy(&(buffer->raw[buffer->pos]), chunk, sizeof(char) * chunk_len);
        buffer->pos += chunk_len;

        // flush buffer to write method
        if (buffer->pos >= buffer->len) {
            BAIL_ON_NULL(fp_write_ret = PyObject_CallFunctionObjArgs(buffer->fp_write, buffer->obj, NULL));
            Py_DECREF(fp_write_ret);
            Py_DECREF(buffer->obj);
            buffer->len = BUFFER_FP_SIZE;
            BAIL_ON_NULL(buffer->obj = PyBytes_FromStringAndSize(NULL, buffer->len));
            buffer->raw = PyBytes_AS_STRING(buffer->obj);
            buffer->pos = 0;
        }
    }
    return 0;

bail:
    return 1;
}

// Flushes remaining bytes to writer and returns None or returns final bytes object (when no writer specified).
// Does NOT free passed in buffer struct.
PyObject* _ubjson_encoder_buffer_finalise(_ubjson_encoder_buffer_t *buffer) {
    PyObject *fp_write_ret;

    // shrink buffer to fit
    if (buffer->pos < buffer->len) {
        BAIL_ON_NONZERO(_PyBytes_Resize(&buffer->obj, buffer->pos));
        buffer->len = buffer->pos;
    }
    if (NULL == buffer->fp_write) {
        Py_INCREF(buffer->obj);
        return buffer->obj;
    } else {
        if (buffer->pos > 0) {
            BAIL_ON_NULL(fp_write_ret = PyObject_CallFunctionObjArgs(buffer->fp_write, buffer->obj, NULL));
            Py_DECREF(fp_write_ret);
        }
        Py_RETURN_NONE;
    }

bail:
    return NULL;
}

/******************************************************************************/

static int _encode_PyBytes(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    const char *raw;
    Py_ssize_t len;

    raw = PyBytes_AS_STRING(obj);
    len = PyBytes_GET_SIZE(obj);

    WRITE_OR_BAIL(bytes_array_prefix, sizeof(bytes_array_prefix));
    BAIL_ON_NONZERO(_encode_longlong(len, buffer));
    WRITE_OR_BAIL(raw, len);
    // no ARRAY_END since length was specified

    return 0;

bail:
    return 1;
}

static int _encode_PyByteArray(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    const char *raw;
    Py_ssize_t len;

    raw = PyByteArray_AS_STRING(obj);
    len = PyByteArray_GET_SIZE(obj);

    WRITE_OR_BAIL(bytes_array_prefix, sizeof(bytes_array_prefix));
    BAIL_ON_NONZERO(_encode_longlong(len, buffer));
    WRITE_OR_BAIL(raw, len);
    // no ARRAY_END since length was specified

    return 0;

bail:
    return 1;
}

/******************************************************************************/

static int _encode_PyObject_as_PyDecimal(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    PyObject *decimal = NULL;

    // Decimal class has no public C API
    BAIL_ON_NULL(decimal =  PyObject_CallFunctionObjArgs((PyObject*)PyDec_Type, obj, NULL));
    BAIL_ON_NONZERO(_encode_PyDecimal(decimal, buffer));

    Py_DECREF(decimal);
    return 0;

bail:
    Py_XDECREF(decimal);
    return 1;
}

static int _encode_PyDecimal(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    PyObject *is_finite;
    PyObject *str = NULL;
    PyObject *encoded = NULL;
    const char *raw;
    Py_ssize_t len;

    // Decimal class has no public C API
    BAIL_ON_NULL(is_finite = PyObject_CallMethod(obj, "is_finite", NULL));

    if (Py_True == is_finite) {
#if PY_MAJOR_VERSION >= 3
        BAIL_ON_NULL(str = PyObject_Str(obj));
#else
        BAIL_ON_NULL(str = PyObject_Unicode(obj));
#endif
        BAIL_ON_NULL(encoded = PyUnicode_AsEncodedString(str, "utf-8", NULL));
        raw = PyBytes_AS_STRING(encoded);
        len = PyBytes_GET_SIZE(encoded);

        WRITE_CHAR_OR_BAIL(TYPE_HIGH_PREC);
        BAIL_ON_NONZERO(_encode_longlong(len, buffer));
        WRITE_OR_BAIL(raw, len);
        Py_DECREF(str);
        Py_DECREF(encoded);
    } else {
        WRITE_CHAR_OR_BAIL(TYPE_NULL);
    }

    Py_DECREF(is_finite);
    return 0;

bail:
    Py_XDECREF(is_finite);
    Py_XDECREF(str);
    Py_XDECREF(encoded);
    return 1;
}

/******************************************************************************/

static int _encode_PyUnicode(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    PyObject *str;
    const char *raw;
    Py_ssize_t len;

    BAIL_ON_NULL(str = PyUnicode_AsEncodedString(obj, "utf-8", NULL));
    raw = PyBytes_AS_STRING(str);
    len = PyBytes_GET_SIZE(str);

    if (1 == len) {
        WRITE_CHAR_OR_BAIL(TYPE_CHAR);
    } else {
        WRITE_CHAR_OR_BAIL(TYPE_STRING);
        BAIL_ON_NONZERO(_encode_longlong(len, buffer));
    }
    WRITE_OR_BAIL(raw, len);
    Py_DECREF(str);
    return 0;

bail:
    Py_XDECREF(str);
    return 1;
}

/******************************************************************************/

static int _encode_PyFloat(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    char numtmp[9]; // holds type char + float32/64
    double abs;
    double num = PyFloat_AsDouble(obj);

    if (-1.0 == num && PyErr_Occurred()) {
        goto bail;
    }

#ifdef USE__FPCLASS
    switch (_fpclass(num)) {
        case _FPCLASS_SNAN:
        case _FPCLASS_QNAN:
        case _FPCLASS_NINF:
        case _FPCLASS_PINF:
#else
    switch (fpclassify(num)) {
        case FP_NAN:
        case FP_INFINITE:
#endif
            WRITE_CHAR_OR_BAIL(TYPE_NULL);
            return 0;
#ifdef USE__FPCLASS
        case _FPCLASS_NZ:
        case _FPCLASS_PZ:
#else
        case FP_ZERO:
#endif
            BAIL_ON_NONZERO(_pyfuncs_ubj_PyFloat_Pack4(num, (unsigned char*)&numtmp[1], 0));
            numtmp[0] = TYPE_FLOAT32;
            WRITE_OR_BAIL(numtmp, 5);
            return 0;
#ifdef USE__FPCLASS
        case _FPCLASS_ND:
        case _FPCLASS_PD:
#else
        case FP_SUBNORMAL:
#endif
            BAIL_ON_NONZERO(_encode_PyObject_as_PyDecimal(obj, buffer));
            return 0;
    }

    abs = fabs(num);
    if (!buffer->prefs.no_float32 && 1.18e-38 <= abs && 3.4e38 >= abs) {
        BAIL_ON_NONZERO(_pyfuncs_ubj_PyFloat_Pack4(num, (unsigned char*)&numtmp[1], 0));
        numtmp[0] = TYPE_FLOAT32;
        WRITE_OR_BAIL(numtmp, 5);
    } else {
        BAIL_ON_NONZERO(_pyfuncs_ubj_PyFloat_Pack8(num, (unsigned char*)&numtmp[1], 0));
        numtmp[0] = TYPE_FLOAT64;
        WRITE_OR_BAIL(numtmp, 9);
    }
    return 0;

bail:
    return 1;
}

/******************************************************************************/

#define WRITE_TYPE_AND_INT8_OR_BAIL(c1, c2) {\
    numtmp[0] = c1;\
    numtmp[1] = (char)c2;\
    WRITE_OR_BAIL(numtmp, 2);\
}
#define WRITE_INT_INTO_NUMTMP(num, size) {\
    /* numtmp also stores type, so need one larger*/\
    unsigned char i = size + 1;\
    do {\
        numtmp[--i] = (char)num;\
        num >>= 8;\
    } while (i > 1);\
}
#define WRITE_INT16_OR_BAIL(num) {\
    WRITE_INT_INTO_NUMTMP(num, 2);\
    numtmp[0] = TYPE_INT16;\
    WRITE_OR_BAIL(numtmp, 3);\
}
#define WRITE_INT32_OR_BAIL(num) {\
    WRITE_INT_INTO_NUMTMP(num, 4);\
    numtmp[0] = TYPE_INT32;\
    WRITE_OR_BAIL(numtmp, 5);\
}
#define WRITE_INT64_OR_BAIL(num) {\
    WRITE_INT_INTO_NUMTMP(num, 8);\
    numtmp[0] = TYPE_INT64;\
    WRITE_OR_BAIL(numtmp, 9);\
}

static int _encode_longlong(long long num, _ubjson_encoder_buffer_t *buffer) {
    char numtmp[9]; // large enough to hold type + maximum integer (INT64)

    if (num >= 0) {
        if (num < POWER_TWO(8)) {
            WRITE_TYPE_AND_INT8_OR_BAIL(TYPE_UINT8, num);
        } else if (num < POWER_TWO(15)) {
            WRITE_INT16_OR_BAIL(num);
        } else if (num < POWER_TWO(31)) {
            WRITE_INT32_OR_BAIL(num);
        } else {
            WRITE_INT64_OR_BAIL(num);
        }
    } else if (num >= -(POWER_TWO(7))) {
        WRITE_TYPE_AND_INT8_OR_BAIL(TYPE_INT8, num);
    } else if (num >= -(POWER_TWO(15))) {
        WRITE_INT16_OR_BAIL(num);
    } else if (num >= -(POWER_TWO(31))) {
        WRITE_INT32_OR_BAIL(num);
    } else {
        WRITE_INT64_OR_BAIL(num);
    }
    return 0;

bail:
    return 1;
}

static int _encode_PyLong(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    int overflow;
    long long num = PyLong_AsLongLongAndOverflow(obj, &overflow);

    if (overflow) {
        BAIL_ON_NONZERO(_encode_PyObject_as_PyDecimal(obj, buffer));
        return 0;
    } else if (num == -1 && PyErr_Occurred()) {
        // unexpected as PyLong should fit if not overflowing
        goto bail;
    } else {
        return _encode_longlong(num, buffer);
    }

bail:
    return 1;
}

#if PY_MAJOR_VERSION < 3
static int _encode_PyInt(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    long num = PyInt_AsLong(obj);

    if (num == -1 && PyErr_Occurred()) {
        // unexpected as PyInt should fit into long
        return 1;
    } else {
        return _encode_longlong(num, buffer);
    }
}
#endif

/******************************************************************************/

static int _encode_PySequence(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    PyObject *ident;        // id of sequence (for checking circular reference)
    PyObject *seq = NULL;   // converted sequence (via PySequence_Fast)
    Py_ssize_t len;
    Py_ssize_t i;
    int seen;

    // circular reference check
    BAIL_ON_NULL(ident = PyLong_FromVoidPtr(obj));
    if ((seen = PySet_Contains(buffer->markers, ident))) {
        if (-1 != seen) {
            PyErr_SetString(PyExc_ValueError, "Circular reference detected");
        }
        goto bail;
    }
    BAIL_ON_NONZERO(PySet_Add(buffer->markers, ident));

    BAIL_ON_NULL(seq = PySequence_Fast(obj, "_encode_PySequence expects sequence"));
    len = PySequence_Fast_GET_SIZE(seq);

    WRITE_CHAR_OR_BAIL(ARRAY_START);
    if (buffer->prefs.container_count) {
        WRITE_CHAR_OR_BAIL(CONTAINER_COUNT);
        BAIL_ON_NONZERO(_encode_longlong(len, buffer));
    }

    for (i = 0; i < len; i++) {
        BAIL_ON_NONZERO(_ubjson_encode_value(PySequence_Fast_GET_ITEM(seq, i), buffer));
    }

    if (!buffer->prefs.container_count) {
        WRITE_CHAR_OR_BAIL(ARRAY_END);
    }

    if (-1 == PySet_Discard(buffer->markers, ident)) {
        goto bail;
    }
    Py_DECREF(ident);
    Py_DECREF(seq);
    return 0;

bail:
    Py_XDECREF(ident);
    Py_XDECREF(seq);
    return 1;
}

/******************************************************************************/

static int _encode_mapping_key(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    PyObject *str = NULL;
    const char *raw;
    Py_ssize_t len;

    if (PyUnicode_Check(obj)) {
        BAIL_ON_NULL(str = PyUnicode_AsEncodedString(obj, "utf-8", NULL));
    }
#if PY_MAJOR_VERSION < 3
    else if (PyString_Check(obj)) {
        BAIL_ON_NULL(str = PyString_AsEncodedObject(obj, "utf-8", NULL));
    }
#endif
    else {
        PyErr_SetString(EncoderException, "Mapping keys can only be strings");
        goto bail;
    }

    raw = PyBytes_AS_STRING(str);
    len = PyBytes_GET_SIZE(str);
    BAIL_ON_NONZERO(_encode_longlong(len, buffer));
    WRITE_OR_BAIL(raw, len);
    Py_DECREF(str);
    return 0;

bail:
    Py_XDECREF(str);
    return 1;
}

static int _encode_PyMapping(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    PyObject *ident; // id of sequence (for checking circular reference)
    PyObject *items = NULL;
    PyObject *iter = NULL;
    PyObject *item = NULL;
    int seen;

    // circular reference check
    BAIL_ON_NULL(ident = PyLong_FromVoidPtr(obj));
    if ((seen = PySet_Contains(buffer->markers, ident))) {
        if (-1 != seen) {
            PyErr_SetString(PyExc_ValueError, "Circular reference detected");
        }
        goto bail;
    }
    BAIL_ON_NONZERO(PySet_Add(buffer->markers, ident));

    BAIL_ON_NULL(items = PyMapping_Items(obj));
    if (buffer->prefs.sort_keys) {
        BAIL_ON_NONZERO(PyList_Sort(items));
    }

    WRITE_CHAR_OR_BAIL(OBJECT_START);
    if (buffer->prefs.container_count) {
        WRITE_CHAR_OR_BAIL(CONTAINER_COUNT);
        _encode_longlong(PyList_GET_SIZE(items), buffer);
    }

    BAIL_ON_NULL(iter = PyObject_GetIter(items));
    while (NULL != (item = PyIter_Next(iter))) {
        if (!PyTuple_Check(item) || 2 != PyTuple_GET_SIZE(item)) {
            PyErr_SetString(PyExc_ValueError, "items must return 2-tuples");
            goto bail;
        }
        BAIL_ON_NONZERO(_encode_mapping_key(PyTuple_GET_ITEM(item, 0), buffer));
        BAIL_ON_NONZERO(_ubjson_encode_value(PyTuple_GET_ITEM(item, 1), buffer));
        Py_CLEAR(item);
    }
    // for PyIter_Next
    if (PyErr_Occurred()) {
        goto bail;
    }

    if (!buffer->prefs.container_count) {
        WRITE_CHAR_OR_BAIL(OBJECT_END);
    }

    if (-1 == PySet_Discard(buffer->markers, ident)) {
        goto bail;
    }
    Py_DECREF(iter);
    Py_DECREF(items);
    Py_DECREF(ident);
    return 0;

bail:
    Py_XDECREF(item);
    Py_XDECREF(iter);
    Py_XDECREF(items);
    Py_XDECREF(ident);
    return 1;
}

/******************************************************************************/

int _ubjson_encode_value(PyObject *obj, _ubjson_encoder_buffer_t *buffer) {
    PyObject *newobj = NULL; // result of default call (when encoding unsupported types)

    if (Py_None == obj) {
        WRITE_CHAR_OR_BAIL(TYPE_NULL);
    } else if (Py_True == obj) {
        WRITE_CHAR_OR_BAIL(TYPE_BOOL_TRUE);
    } else if (Py_False == obj) {
        WRITE_CHAR_OR_BAIL(TYPE_BOOL_FALSE);
    } else if (PyUnicode_Check(obj)) {
        BAIL_ON_NONZERO(_encode_PyUnicode(obj, buffer));
#if PY_MAJOR_VERSION < 3
    } else if (PyInt_Check(obj)) {
        BAIL_ON_NONZERO(_encode_PyInt(obj, buffer));
#endif
    } else if (PyLong_Check(obj)) {
        BAIL_ON_NONZERO(_encode_PyLong(obj, buffer));
    } else if (PyFloat_Check(obj)) {
        BAIL_ON_NONZERO(_encode_PyFloat(obj, buffer));
    } else if (PyDec_Check(obj)) {
        BAIL_ON_NONZERO(_encode_PyDecimal(obj, buffer));
    } else if (PyBytes_Check(obj)) {
        BAIL_ON_NONZERO(_encode_PyBytes(obj, buffer));
    } else if (PyByteArray_Check(obj)) {
        BAIL_ON_NONZERO(_encode_PyByteArray(obj, buffer));
    // order important since Mapping could also be Sequence
    } else if (PyMapping_Check(obj)
    // Unfortunately PyMapping_Check is no longer enough, see https://bugs.python.org/issue5945
#if PY_MAJOR_VERSION >= 3
               && PyObject_HasAttrString(obj, "items")
#endif
    ) {
        RECURSE_AND_BAIL_ON_NONZERO(_encode_PyMapping(obj, buffer), " while encoding a UBJSON object");
    } else if (PySequence_Check(obj)) {
        RECURSE_AND_BAIL_ON_NONZERO(_encode_PySequence(obj, buffer), " while encoding a UBJSON array");
    } else if (NULL == obj) {
        PyErr_SetString(PyExc_RuntimeError, "Internal error - _ubjson_encode_value got NULL obj");
        goto bail;
    } else if (NULL != buffer->prefs.default_func) {
        BAIL_ON_NULL(newobj = PyObject_CallFunctionObjArgs(buffer->prefs.default_func, obj, NULL));
        RECURSE_AND_BAIL_ON_NONZERO(_ubjson_encode_value(newobj, buffer), " while encoding with default function");
        Py_DECREF(newobj);
    } else {
        PyErr_Format(EncoderException, "Cannot encode item of type %s", obj->ob_type->tp_name);
        goto bail;
    }
    return 0;

bail:
    Py_XDECREF(newobj);
    return 1;
}


int _ubjson_encoder_init(void) {
    PyObject *tmp_module = NULL;
    PyObject *tmp_obj = NULL;

    // try to determine floating point format / endianess
    _pyfuncs_ubj_detect_formats();

    // allow encoder to access EncoderException & Decimal class
    BAIL_ON_NULL(tmp_module = PyImport_ImportModule("ubjson.encoder"));
    BAIL_ON_NULL(EncoderException = PyObject_GetAttrString(tmp_module, "EncoderException"));
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
    Py_CLEAR(EncoderException);
    Py_CLEAR(PyDec_Type);
    Py_XDECREF(tmp_obj);
    Py_XDECREF(tmp_module);
    return 1;
}


void _ubjson_encoder_cleanup(void) {
    Py_CLEAR(EncoderException);
    Py_CLEAR(PyDec_Type);
}
