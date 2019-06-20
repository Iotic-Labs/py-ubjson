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

#define TYPE_NONE '\0' // Used internally only, not part of ubjson specification
#define TYPE_NULL 'Z'
#define TYPE_NOOP 'N'
#define TYPE_BOOL_TRUE 'T'
#define TYPE_BOOL_FALSE 'F'
#define TYPE_INT8 'i'
#define TYPE_UINT8 'U'
#define TYPE_INT16 'I'
#define TYPE_INT32 'l'
#define TYPE_INT64 'L'
#define TYPE_FLOAT32 'd'
#define TYPE_FLOAT64 'D'
#define TYPE_HIGH_PREC 'H'
#define TYPE_CHAR 'C'
#define TYPE_STRING 'S'
// Container delimiters
#define OBJECT_START '{'
#define OBJECT_END '}'
#define ARRAY_START '['
#define ARRAY_END ']'
// Optional container parameters
#define CONTAINER_TYPE '$'
#define CONTAINER_COUNT '#'

#if defined (__cplusplus)
}
#endif
