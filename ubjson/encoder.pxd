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


"""UBJSON encoder (cython annotations)"""

import cython


from .markers cimport (TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32,
                       TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING, OBJECT_START,
                       OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)

cdef dict __SMALL_INTS_ENCODED
cdef dict __SMALL_UINTS_ENCODED
cdef bytes __BYTES_ARRAY_PREFIX


cdef void __encode_high_prec(fp_write, item) except *


cdef void __encode_decimal(fp_write, item) except *


cdef void __encode_int(fp_write, item) except *


cdef void __encode_float(fp_write, item) except *


cdef void __encode_float64(fp_write, item) except *


cdef void __encode_string(fp_write, item) except *


cdef void __encode_bytes(fp_write, item) except *


@cython.locals(no_float32=cython.bint)
cdef bint __encode_value(fp_write, item, no_float32) except *


@cython.locals(seen_containers=dict, container_count=cython.bint, sort_keys=cython.bint, container_id=cython.ulonglong,
               no_float32=cython.bint)
cdef void __encode_array(fp_write, item, seen_containers, container_count, sort_keys, no_float32) except *


@cython.locals(seen_containers=dict, container_count=cython.bint, sort_keys=cython.bint, container_id=cython.ulonglong,
               no_float32=cython.bint)
cdef void __encode_object(fp_write, item, seen_containers, container_count, sort_keys, no_float32) except *


@cython.locals(container_count=cython.bint, sort_keys=cython.bint, no_float32=cython.bint)
cpdef void dump(obj, fp, container_count=*, sort_keys=*, no_float32=*) except *


@cython.locals(container_count=cython.bint, sort_keys=cython.bint, no_float32=cython.bint)
cpdef object dumpb(obj, container_count=*, sort_keys=*, no_float32=*)
