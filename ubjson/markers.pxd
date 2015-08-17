# Copyright (c) 2015, V. Termanis, Iotic Labs Ltd.
# All rights reserved.
# Licensed under 2-clause BSD license - see LICENSE file for details.

"""UBJSON marker defitions (cython annotations)"""

cdef bytes TYPE_NONE = b'\x00'
cdef bytes TYPE_NULL = b'Z'
cdef bytes TYPE_BOOL_TRUE = b'T'
cdef bytes TYPE_BOOL_FALSE = b'F'
cdef bytes TYPE_INT8 = b'i'
cdef bytes TYPE_UINT8 = b'U'
cdef bytes TYPE_INT16 = b'I'
cdef bytes TYPE_INT32 = b'l'
cdef bytes TYPE_INT64 = b'L'
cdef bytes TYPE_FLOAT32 = b'd'
cdef bytes TYPE_FLOAT64 = b'D'
cdef bytes TYPE_HIGH_PREC = b'H'
cdef bytes TYPE_CHAR = b'C'
cdef bytes TYPE_STRING = b'S'
cdef bytes OBJECT_START = b'{'
cdef bytes OBJECT_END = b'}'
cdef bytes ARRAY_START = b'['
cdef bytes ARRAY_END = b']'
cdef bytes CONTAINER_TYPE = b'$'
cdef bytes CONTAINER_COUNT = b'#'
