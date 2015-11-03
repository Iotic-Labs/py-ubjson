# Copyright (c) 2015 Iotic Labs Ltd. All rights reserved.

"""Non-resursive UBJSON decoder. (cython annotations)"""

import cython


from .markers cimport (TYPE_NONE, TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16,
                       TYPE_INT32, TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING,
                       OBJECT_START, OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)


cdef frozenset __TYPES = frozenset((TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16,
                                    TYPE_INT32, TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR,
                                    TYPE_STRING))
cdef frozenset __TYPES_NO_DATA = frozenset((TYPE_NULL, TYPE_BOOL_FALSE, TYPE_BOOL_TRUE))


cdef dict __INT_MAPPING = {TYPE_UINT8: (1, '>B'),
                           TYPE_INT8: (1, '>b'),
                           TYPE_INT16: (2, '>h'),
                           TYPE_INT32: (4, '>i'),
                           TYPE_INT64: (8, '>q')}


@cython.locals(marker=bytes, length=int, raw=bytes)
cdef object __decode_high_prec(fp_read, marker)


@cython.locals(marker=bytes, length=int, fmt=str)
cdef object __decode_int(fp_read, marker)


@cython.locals(marker=bytes)
cdef object __decode_float(fp_read, marker)


@cython.locals(marker=bytes, raw=bytes)
cdef unicode __decode_char(fp_read, marker)


@cython.locals(marker=bytes, length=int, raw=bytes)
cdef unicode __decode_string(fp_read, marker)


@cython.locals(marker=bytes, length=int, raw=bytes)
cdef unicode __decode_object_key(fp_read, marker)


@cython.locals(in_mapping=cython.bint, no_bytes=cython.bint, next_byte=bytes, type_=bytes, count=int)
cdef object __get_container_params(fp_read, in_mapping, no_bytes, object_pairs_hook)


@cython.locals(in_mapping=cython.bint, no_bytes=cython.bint, marker=bytes, counting=cython.bint, count=int, type_=bytes)
cdef object __decode_container(fp_read, in_mapping, no_bytes, object_pairs_hook)


@cython.locals(no_bytes=cython.bint, marker=bytes)
cpdef object load(fp, no_bytes=*, object_pairs_hook=*)


@cython.locals(no_bytes=cython.bint)
cpdef object loadb(chars, no_bytes=*, object_pairs_hook=*)
