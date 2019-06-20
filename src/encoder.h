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

#pragma once

#if defined (__cplusplus)
extern "C" {
#endif

#include <Python.h>

/******************************************************************************/

typedef struct {
    PyObject *default_func;
    int container_count;
    int sort_keys;
    int no_float32;
} _ubjson_encoder_prefs_t;

typedef struct {
    // holds PyBytes instance (buffer)
    PyObject *obj;
    // raw access to obj, size & position
    char* raw;
    size_t len;
    size_t pos;
    // if not NULL, full buffer will be written to this method
    PyObject *fp_write;
    // PySet of sequences and mappings for detecting a circular reference
    PyObject *markers;
    _ubjson_encoder_prefs_t prefs;
} _ubjson_encoder_buffer_t;

/******************************************************************************/

extern _ubjson_encoder_buffer_t* _ubjson_encoder_buffer_create(_ubjson_encoder_prefs_t* prefs, PyObject *fp_write);
extern void _ubjson_encoder_buffer_free(_ubjson_encoder_buffer_t **buffer);
extern PyObject* _ubjson_encoder_buffer_finalise(_ubjson_encoder_buffer_t *buffer);
extern int _ubjson_encode_value(PyObject *obj, _ubjson_encoder_buffer_t *buffer);
extern int _ubjson_encoder_init(void);
extern void _ubjson_encoder_cleanup(void);

#if defined (__cplusplus)
}
#endif
