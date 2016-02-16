# Copyright (c) 2016 Iotic Labs Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/Iotic-Labs/py-ubjson/blob/master/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""UBJSON decoder. (cython annotations)"""

import cython

from .markers cimport (TYPE_NONE, TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16,
                       TYPE_INT32, TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING,
                       OBJECT_START, OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)

cdef frozenset __TYPES
cdef frozenset __TYPES_NO_DATA
cdef frozenset __TYPES_INT
cdef dict __SMALL_INTS_DECODED
cdef dict __SMALL_UINTS_DECODED


@cython.locals(marker=bytes, length=int, raw=bytes)
cdef object __decode_high_prec(fp_read, marker)


@cython.locals(marker=bytes, value=int)
cdef object __decode_int_non_negative(fp_read, marker)


@cython.locals(marker=bytes)
cdef object __decode_int8(fp_read, marker)


@cython.locals(marker=bytes)
cdef object __decode_uint8(fp_read, marker)


@cython.locals(marker=bytes)
cdef object __decode_int16(fp_read, marker)


@cython.locals(marker=bytes)
cdef object __decode_int32(fp_read, marker)


@cython.locals(marker=bytes)
cdef object __decode_int64(fp_read, marker)


@cython.locals(marker=bytes)
cdef object __decode_float32(fp_read, marker)


@cython.locals(marker=bytes)
cdef object __decode_float64(fp_read, marker)


@cython.locals(marker=bytes, raw=bytes)
cdef unicode __decode_char(fp_read, marker)


@cython.locals(marker=bytes, length=int, raw=bytes)
cdef unicode __decode_string(fp_read, marker)


@cython.locals(marker=bytes, length=int, raw=bytes)
cdef unicode __decode_object_key(fp_read, marker)


@cython.locals(in_mapping=cython.bint, no_bytes=cython.bint, marker=bytes, type_=bytes, count=int)
cdef object __get_container_params(fp_read, in_mapping, no_bytes, object_pairs_hook)


@cython.locals(no_bytes=cython.bint, marker=bytes, counting=cython.bint, count=int, type_=bytes)
cdef object __decode_object(fp_read, no_bytes, object_pairs_hook)


@cython.locals(no_bytes=cython.bint, marker=bytes, counting=cython.bint, count=int, type_=bytes)
cdef object __decode_array(fp_read, no_bytes, object_pairs_hook)


@cython.locals(no_bytes=cython.bint, marker=bytes)
cpdef object load(fp, no_bytes=*, object_pairs_hook=*)


@cython.locals(no_bytes=cython.bint)
cpdef object loadb(chars, no_bytes=*, object_pairs_hook=*)
