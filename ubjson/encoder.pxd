# Copyright (c) 2015 Iotic Labs Ltd. All rights reserved.

"""Non-resursive UBJSON encoder (cython annotations)"""

import cython


from .markers cimport (TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32,
                       TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING, OBJECT_START,
                       OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)


cdef void __encode_high_prec(fp_write, item)


cdef void __encode_decimal(fp_write, item)


cdef void __encode_int(fp_write, item)


cdef void __encode_float(fp_write, item)


cdef void __encode_string(fp_write, item)


cdef void __encode_object_key(fp_write, key)


cdef void __encode_bytes(fp_write, item)


cdef bint __encode_value(fp_write, item)


@cython.locals(in_mapping=cython.bint, seen_containers=dict, container_count=cython.bint, sort_keys=cython.bint,
               container_id=cython.ulonglong)
cdef int __encode_container(fp_write, obj, in_mapping, seen_containers, container_count, sort_keys) except -1


@cython.locals(container_count=cython.bint, sort_keys=cython.bint)
cdef int __dump(obj, fp_write, container_count, sort_keys) except -1


@cython.locals(container_count=cython.bint, sort_keys=cython.bint)
cpdef int dump(obj, fp, container_count=*, sort_keys=*) except -1


@cython.locals(container_count=cython.bint, sort_keys=cython.bint)
cpdef object dumpb(obj, container_count=*, sort_keys=*)
