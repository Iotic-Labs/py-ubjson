# Copyright (c) 2015, V. Termanis, Iotic Labs Ltd.
# All rights reserved.
# Licensed under 2-clause BSD license - see LICENSE file for details.

"""UBJSON marker defitions"""

# Value types
TYPE_NONE = b'\x00'  # Used internally only, not part of ubjson specification
TYPE_NULL = b'Z'
TYPE_BOOL_TRUE = b'T'
TYPE_BOOL_FALSE = b'F'
TYPE_INT8 = b'i'
TYPE_UINT8 = b'U'
TYPE_INT16 = b'I'
TYPE_INT32 = b'l'
TYPE_INT64 = b'L'
TYPE_FLOAT32 = b'd'
TYPE_FLOAT64 = b'D'
TYPE_HIGH_PREC = b'H'
TYPE_CHAR = b'C'
TYPE_STRING = b'S'

# Container delimiters
OBJECT_START = b'{'
OBJECT_END = b'}'
ARRAY_START = b'['
ARRAY_END = b']'

# Optional container parameters
CONTAINER_TYPE = b'$'
CONTAINER_COUNT = b'#'
