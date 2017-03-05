/*
 * Copyright (c) 2017 Iotic Labs Ltd. All rights reserved.
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

#include "common.h"
#include "encoder.h"
#include "decoder.h"

/******************************************************************************/

// container_count, sort_keys, no_float32
static _ubjson_encoder_prefs_t _ubjson_encoder_prefs_defaults = { 0, 0, 1 };

// no_bytes, object_pairs_hook
static _ubjson_decoder_prefs_t _ubjson_decoder_prefs_defaults = { NULL, 0 };

/******************************************************************************/

PyDoc_STRVAR(_ubjson_dump__doc__, "See pure Python version (encoder.dump) for documentation.");
#define FUNC_DEF_DUMP {"dump", (PyCFunction)_ubjson_dump, METH_VARARGS | METH_KEYWORDS, _ubjson_dump__doc__}
static PyObject*
_ubjson_dump(PyObject *self, PyObject *args, PyObject *kwargs) {
    static const char *format = "OO|iii:dump";
    static char *keywords[] = {"obj", "fp", "container_count", "sort_keys", "no_float32", NULL};

    _ubjson_encoder_buffer_t *buffer = NULL;
    _ubjson_encoder_prefs_t prefs = _ubjson_encoder_prefs_defaults;
    PyObject *obj;
    PyObject *fp;
    PyObject *fp_write = NULL;
    UNUSED(self);

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, format, keywords, &obj, &fp, &prefs.container_count,
                                     &prefs.sort_keys, &prefs.no_float32)) {
        goto bail;
    }
    BAIL_ON_NULL(fp_write = PyObject_GetAttrString(fp, "write"));
    BAIL_ON_NULL(buffer = _ubjson_encoder_buffer_create(&prefs, fp_write));
    // buffer creation has added reference
    Py_CLEAR(fp_write);

    BAIL_ON_NONZERO(_ubjson_encode_value(obj, buffer));
    BAIL_ON_NULL(obj = _ubjson_encoder_buffer_finalise(buffer));
    _ubjson_encoder_buffer_free(buffer);
    return obj;

bail:
    Py_XDECREF(fp_write);
    _ubjson_encoder_buffer_free(buffer);
    return NULL;
}

PyDoc_STRVAR(_ubjson_dumpb__doc__, "See pure Python version (encoder.dumpb) for documentation.");
#define FUNC_DEF_DUMPB {"dumpb", (PyCFunction)_ubjson_dumpb, METH_VARARGS | METH_KEYWORDS, _ubjson_dumpb__doc__}
static PyObject*
_ubjson_dumpb(PyObject *self, PyObject *args, PyObject *kwargs) {
    static const char *format = "O|iii:dumpb";
    static char *keywords[] = {"obj", "container_count", "sort_keys", "no_float32", NULL};

    _ubjson_encoder_buffer_t *buffer = NULL;
    _ubjson_encoder_prefs_t prefs = _ubjson_encoder_prefs_defaults;
    PyObject *obj;
    UNUSED(self);

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, format, keywords, &obj, &prefs.container_count, &prefs.sort_keys,
                                     &prefs.no_float32)) {
        goto bail;
    }

    BAIL_ON_NULL(buffer = _ubjson_encoder_buffer_create(&prefs, NULL));
    BAIL_ON_NONZERO(_ubjson_encode_value(obj, buffer));
    BAIL_ON_NULL(obj = _ubjson_encoder_buffer_finalise(buffer));
    _ubjson_encoder_buffer_free(buffer);
    return obj;

bail:
    _ubjson_encoder_buffer_free(buffer);
    return NULL;
}

/******************************************************************************/

PyDoc_STRVAR(_ubjson_load__doc__, "See pure Python version (encoder.load) for documentation.");
#define FUNC_DEF_LOAD {"load", (PyCFunction)_ubjson_load, METH_VARARGS | METH_KEYWORDS, _ubjson_load__doc__}
static PyObject*
_ubjson_load(PyObject *self, PyObject *args, PyObject *kwargs) {
    static const char *format = "O|iO:load";
    static char *keywords[] = {"fp", "no_bytes", "object_pairs_hook", NULL};

    _ubjson_decoder_buffer_t *buffer = NULL;
    _ubjson_decoder_prefs_t prefs = _ubjson_decoder_prefs_defaults;
    PyObject *fp;
    PyObject *fp_read = NULL;
    PyObject *obj = NULL;
    UNUSED(self);

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, format, keywords, &fp, &prefs.no_bytes, &prefs.object_pairs_hook)) {
        goto bail;
    }
    BAIL_ON_NULL(fp_read = PyObject_GetAttrString(fp, "read"));
    if (!PyCallable_Check(fp_read)) {
        PyErr_SetString(PyExc_TypeError, "fp.read not callable");
        goto bail;
    }

    BAIL_ON_NULL(buffer = _ubjson_decoder_buffer_create(&prefs, fp_read));
    // buffer creation has added reference
    Py_CLEAR(fp_read);

    BAIL_ON_NULL(obj = _ubjson_decode_value(buffer, NULL));
    _ubjson_decoder_buffer_free(buffer);
    return obj;

bail:
    Py_XDECREF(fp_read);
    _ubjson_decoder_buffer_free(buffer);
    return NULL;
}

PyDoc_STRVAR(_ubjson_loadb__doc__, "See pure Python version (encoder.loadb) for documentation.");
#define FUNC_DEF_LOADB {"loadb", (PyCFunction)_ubjson_loadb, METH_VARARGS | METH_KEYWORDS, _ubjson_loadb__doc__}
static PyObject*
_ubjson_loadb(PyObject *self, PyObject *args, PyObject *kwargs) {
    static const char *format = "O|iO:loadb";
    static char *keywords[] = {"chars", "no_bytes", "object_pairs_hook", NULL};

    _ubjson_decoder_buffer_t *buffer = NULL;
    _ubjson_decoder_prefs_t prefs = _ubjson_decoder_prefs_defaults;
    PyObject *chars;
    PyObject *obj = NULL;
    UNUSED(self);

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, format, keywords, &chars, &prefs.no_bytes,
                                     &prefs.object_pairs_hook)) {
        goto bail;
    }
    if (PyUnicode_Check(chars)) {
        PyErr_SetString(PyExc_TypeError, "chars must be a bytes-like object, not str");
        goto bail;
    }
    if (!PyObject_CheckBuffer(chars)) {
        PyErr_SetString(PyExc_TypeError, "chars does not support buffer interface");
        goto bail;
    }

    BAIL_ON_NULL(buffer = _ubjson_decoder_buffer_create(&prefs, chars));

    BAIL_ON_NULL(obj = _ubjson_decode_value(buffer, NULL));
    _ubjson_decoder_buffer_free(buffer);
    return obj;

bail:
    _ubjson_decoder_buffer_free(buffer);
    return NULL;
}

/******************************************************************************/

static PyMethodDef UbjsonMethods[] = {
    FUNC_DEF_DUMP, FUNC_DEF_DUMPB,
    FUNC_DEF_LOAD, FUNC_DEF_LOADB,
    {NULL, NULL, 0, NULL}
};

#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "_ubjson",
        NULL,
        -1,
        UbjsonMethods,
        NULL,
        NULL,
        NULL,
        NULL
};

#define INITERROR return NULL
PyObject*
PyInit__ubjson(void)

#else
#define INITERROR return

void
init_ubjson(void)
#endif
{
#if PY_MAJOR_VERSION >= 3
    PyObject *module = PyModule_Create(&moduledef);
#else
    PyObject *module = Py_InitModule("_ubjson", UbjsonMethods);
#endif

    BAIL_ON_NONZERO(_ubjson_encoder_init());
    BAIL_ON_NONZERO(_ubjson_decoder_init());

#if PY_MAJOR_VERSION >= 3
    return module;
#else
    return;
#endif

bail:
    _ubjson_encoder_cleanup();
    _ubjson_decoder_cleanup();
    Py_XDECREF(module);
    INITERROR;
}
