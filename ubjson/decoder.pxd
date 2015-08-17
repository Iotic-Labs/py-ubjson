# Copyright (c) 2015, V. Termanis, Iotic Labs Ltd.
# All rights reserved.
# Licensed under 2-clause BSD license - see LICENSE file for details.

"""Non-resursive UBJSON decoder. (cython annotations)"""

import cython


from .markers cimport (TYPE_NONE, TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16,
                       TYPE_INT32, TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING,
                       OBJECT_START, OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)


cdef frozenset __containerTypeStarts = frozenset((ARRAY_START, OBJECT_START))
cdef frozenset __types = frozenset((TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16,
                                    TYPE_INT32, TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR,
                                    TYPE_STRING))
cdef frozenset __typesNoData = frozenset((TYPE_NULL, TYPE_BOOL_FALSE, TYPE_BOOL_TRUE))


cdef dict __intMapping = {TYPE_UINT8: (1, '>B'),
                          TYPE_INT8: (1, '>b'),
                          TYPE_INT16: (2, '>h'),
                          TYPE_INT32: (4, '>i'),
                          TYPE_INT64: (8, '>q')}


@cython.locals(marker=bytes, length=int, raw=bytes)
cdef object __decodeHighPrec(fp, marker)


@cython.locals(marker=bytes, length=int, fmt=str)
cdef object __decodeInt(fp, marker)


@cython.locals(marker=bytes)
cdef object __decodeFloat(fp, marker)


@cython.locals(marker=bytes, raw=bytes)
cdef unicode __decodeChar(fp, marker)


@cython.locals(marker=bytes, length=int, raw=bytes)
cdef unicode __decodeString(fp, marker)


@cython.locals(marker=bytes, length=int, raw=bytes)
cdef unicode __decodeObjectKey(fp, marker)


@cython.locals(inMapping=cython.bint, noBytes=cython.bint, nextByte=bytes, type_=bytes, count=int)
cdef object __getContainerParams(fp, inMapping, noBytes)


@cython.locals(inMapping=cython.bint, noBytes=cython.bint, marker=bytes, counting=cython.bint, count=int, type_=bytes)
cdef object __decodeContainer(fp, inMapping, noBytes)


@cython.locals(no_bytes=cython.bint, marker=bytes)
cpdef object load(fp, no_bytes=*)


@cython.locals(no_bytes=cython.bint)
cpdef object loadb(chars, no_bytes=*)
