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
    PyObject *object_hook;
    PyObject *object_pairs_hook;
    // don't convert UINT8 arrays to bytes instances (and keep as an array of individual integers)
    int no_bytes;
    int intern_object_keys;
} _ubjson_decoder_prefs_t;

typedef struct _ubjson_decoder_buffer_t {
    // either supports buffer interface or is callable returning bytes
    PyObject *input;
    // NULL unless input supports seeking in which case expecting callable with signature of io.IOBase.seek()
    PyObject *seek;
    // function used to read data from this buffer with (depending on whether fixed, callable or seekable)
    const char* (*read_func)(struct _ubjson_decoder_buffer_t *buffer, Py_ssize_t *len, char *dst_buffer);
    // buffer protocol access to raw bytes of input
    Py_buffer view;
    // whether view will need to be released
    int view_set;
    // current position in view
    Py_ssize_t pos;
    // total bytes supplied to user (same as pos in case where callable not used)
    Py_ssize_t total_read;
    // temporary destination buffer if required read larger than currently available input
    char *tmp_dst;
    _ubjson_decoder_prefs_t prefs;
} _ubjson_decoder_buffer_t;

/******************************************************************************/

extern _ubjson_decoder_buffer_t* _ubjson_decoder_buffer_create(_ubjson_decoder_prefs_t* prefs,
                                                               PyObject *input, PyObject *seek);
extern int _ubjson_decoder_buffer_free(_ubjson_decoder_buffer_t **buffer);
extern int _ubjson_decoder_init(void);
// note: marker argument only used internally - supply NULL
extern PyObject* _ubjson_decode_value(_ubjson_decoder_buffer_t *buffer, char *given_marker);
extern void _ubjson_decoder_cleanup(void);

#if defined (__cplusplus)
}
#endif
