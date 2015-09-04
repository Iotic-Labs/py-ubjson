# Copyright (c) 2015, Iotic Labs Ltd.
# All rights reserved.
# Licensed under 2-clause BSD license - see LICENSE file for details.

"""Non-resursive UBJSON encoder (cython annotations)"""

import cython


from .markers cimport (TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32,
                       TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING, OBJECT_START,
                       OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)


cdef void __encodeHighPrec(fpWrite, item)


cdef void __encodeDecimal(fpWrite, item)


cdef void __encodeInt(fpWrite, item)


cdef void __encodeFloat(fpWrite, item)


cdef void __encodeString(fpWrite, item)


cdef void __encodeObjectKey(fpWrite, key)


cdef void __encodeBytes(fpWrite, item)


cdef bint __encodeValue(fpWrite, item)


@cython.locals(inMapping=cython.bint, seenContainers=dict, containerCount=cython.bint, sortKeys=cython.bint,
               containerId=cython.ulonglong)
cdef int __encodeContainer(fpWrite, obj, inMapping, seenContainers, containerCount, sortKeys) except -1


@cython.locals(container_count=cython.bint, sort_keys=cython.bint)
cdef int __dump(obj, fpWrite, container_count, sort_keys) except -1


@cython.locals(container_count=cython.bint, sort_keys=cython.bint)
cpdef int dump(obj, fp, container_count=*, sort_keys=*) except -1


@cython.locals(container_count=cython.bint, sort_keys=cython.bint)
cpdef object dumpb(obj, container_count=*, sort_keys=*)
