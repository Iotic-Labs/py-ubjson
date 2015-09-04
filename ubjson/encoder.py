# Copyright (c) 2015, Iotic Labs Ltd.
# All rights reserved.
# Licensed under 2-clause BSD license - see LICENSE file for details.

"""Non-resursive UBJSON encoder"""

from collections import deque
from struct import pack
from decimal import Decimal
from io import BytesIO

from .compat import Mapping, Sequence, integer_types, unicode_type, text_types, bytes_types
try:
    from .markers import (TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32,
                          TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING, OBJECT_START,
                          OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)
    # encoder.pxd defines these when C extension is enabled
except ImportError:  # pragma: no cover
    pass


class EncoderException(TypeError):
    """Raised when encoding of an object fails."""
    pass


def __encodeHighPrec(fpWrite, item):
    fpWrite(TYPE_HIGH_PREC)
    encodedVal = str(Decimal(item)).encode('utf-8')
    __encodeInt(fpWrite, len(encodedVal))
    fpWrite(encodedVal)


def __encodeDecimal(fpWrite, item):
    fpWrite(TYPE_HIGH_PREC)
    encodedVal = str(item).encode('utf-8')
    __encodeInt(fpWrite, len(encodedVal))
    fpWrite(encodedVal)


def __encodeInt(fpWrite, item):
    if item >= 0:
        if item <= 255:
            fpWrite(TYPE_UINT8)
            fpWrite(pack('>B', item))
        elif item <= 32767:
            fpWrite(TYPE_INT16)
            fpWrite(pack('>h', item))
        elif item <= 2147483647:
            fpWrite(TYPE_INT32)
            fpWrite(pack('>i', item))
        elif item <= 9223372036854775807:
            fpWrite(TYPE_INT64)
            fpWrite(pack('>q', item))
        else:
            __encodeHighPrec(fpWrite, item)
    elif item >= -128:
        fpWrite(TYPE_INT8)
        fpWrite(pack('>b', item))
    elif item >= -32768:
        fpWrite(TYPE_INT16)
        fpWrite(pack('>h', item))
    elif item >= -2147483648:
        fpWrite(TYPE_INT32)
        fpWrite(pack('>i', item))
    elif item >= -9223372036854775808:
        fpWrite(TYPE_INT64)
        fpWrite(pack('>q', item))
    else:
        __encodeHighPrec(fpWrite, item)


def __encodeFloat(fpWrite, item):
    if 1.18e-38 <= abs(item) <= 3.4e38 or item == 0:
        fpWrite(TYPE_FLOAT32)
        fpWrite(pack('>f', item))
    elif 2.23e-308 <= abs(item) < 1.8e308:
        fpWrite(TYPE_FLOAT64)
        fpWrite(pack('>d', item))
    else:
        __encodeHighPrec(fpWrite, item)


def __encodeString(fpWrite, item):
    encodedVal = item.encode('utf-8')
    length = len(encodedVal)
    if length == 1:
        fpWrite(TYPE_CHAR)
    else:
        fpWrite(TYPE_STRING)
        __encodeInt(fpWrite, length)
    fpWrite(encodedVal)


# similar to encodeString, except 'S' marker is not added
def __encodeObjectKey(fpWrite, key):
    encodedVal = key.encode('utf-8') if isinstance(key, unicode_type) else key
    __encodeInt(fpWrite, len(encodedVal))
    fpWrite(encodedVal)


def __encodeBytes(fpWrite, item):
    fpWrite(ARRAY_START)
    fpWrite(CONTAINER_TYPE)
    fpWrite(TYPE_UINT8)
    fpWrite(CONTAINER_COUNT)
    __encodeInt(fpWrite, len(item))
    fpWrite(item)
    # no ARRAY_END since length was specified


def __encodeValue(fpWrite, item):
    if isinstance(item, unicode_type):
        __encodeString(fpWrite, item)

    elif item is None:
        fpWrite(TYPE_NULL)

    elif item is True:
        fpWrite(TYPE_BOOL_TRUE)

    elif item is False:
        fpWrite(TYPE_BOOL_FALSE)

    elif isinstance(item, integer_types):
        __encodeInt(fpWrite, item)

    elif isinstance(item, float):
        __encodeFloat(fpWrite, item)

    elif isinstance(item, Decimal):
        __encodeDecimal(fpWrite, item)

    elif isinstance(item, bytes_types):
        __encodeBytes(fpWrite, item)

    else:
        return False

    return True


# pylint: disable=too-many-branches,too-many-statements
def __encodeContainer(fpWrite, obj, inMapping, seenContainers, containerCount, sortKeys):  # noqa (complexity)
    """Performs encoding within an array or object"""
    # stack for keeping track of sequences and mappings without requiring recursion
    stack = deque()
    # current object being encoded
    current = obj
    containerId = 0

    while True:
        # Get next item from container (or finish container and return to parent)
        if inMapping:
            try:
                key, item = next(current)
            except StopIteration:
                try:
                    inMapping, current, containerId = stack.pop()
                except IndexError:
                    # top-level container reached
                    break
                else:
                    if not containerCount:
                        fpWrite(OBJECT_END)
                    # for circular reference checking
                    del seenContainers[containerId]
                    continue
            # allow both str & unicode for Python 2
            if isinstance(key, text_types):
                __encodeObjectKey(fpWrite, key)
            else:
                raise EncoderException('Mapping keys can only be strings')
        else:
            # sequence
            try:
                item = next(current)
            except StopIteration:
                try:
                    inMapping, current, containerId = stack.pop()
                except IndexError:
                    # top-level container reached
                    break
                else:
                    if not containerCount:
                        fpWrite(ARRAY_END)
                    # for circular reference checking
                    del seenContainers[containerId]
                    continue

        if not __encodeValue(fpWrite, item):
            # order important since mappings could also be sequences
            if isinstance(item, Mapping):
                # circular reference check
                containerId = id(item)
                if containerId in seenContainers:
                    raise EncoderException('Circular reference detected')
                seenContainers[containerId] = item

                fpWrite(OBJECT_START)
                if containerCount:
                    fpWrite(CONTAINER_COUNT)
                    __encodeInt(fpWrite, len(item))
                stack.append((inMapping, current, containerId))
                current = iter(sorted(item.items()) if sortKeys else item.items())
                inMapping = True

            elif isinstance(item, Sequence):
                # circular reference check
                containerId = id(item)
                if containerId in seenContainers:
                    raise EncoderException('Circular reference detected')
                seenContainers[containerId] = item

                fpWrite(ARRAY_START)
                if containerCount:
                    fpWrite(CONTAINER_COUNT)
                    __encodeInt(fpWrite, len(item))
                stack.append((inMapping, current, containerId))
                current = iter(item)
                inMapping = False

            else:
                raise EncoderException('Cannot encode item of type %s' % type(item))


def __dump(obj, fpWrite, container_count, sort_keys):  # noqa (complexity)
    if not __encodeValue(fpWrite, obj):
        # order important since mappings could also be sequences
        if isinstance(obj, Mapping):
            fpWrite(OBJECT_START)
            if container_count:
                fpWrite(CONTAINER_COUNT)
                __encodeInt(fpWrite, len(obj))
            __encodeContainer(fpWrite, iter(sorted(obj.items()) if sort_keys else obj.items()), True, {id(obj): obj},
                              container_count, sort_keys)
            if not container_count:
                fpWrite(OBJECT_END)

        elif isinstance(obj, Sequence):
            fpWrite(ARRAY_START)
            if container_count:
                fpWrite(CONTAINER_COUNT)
                __encodeInt(fpWrite, len(obj))
            __encodeContainer(fpWrite, iter(obj), False, {id(obj): obj}, container_count, sort_keys)
            if not container_count:
                fpWrite(ARRAY_END)

        else:
            raise EncoderException('Cannot encode item of type %s' % type(obj))


def dump(obj, fp, container_count=False, sort_keys=False):
    """Writes the given object as UBJSON to the provided file-like object

    Args:
        obj: The object to encode
        fp: write([size])-able object
        container_count (bool): Specify length for container types (including
                                for empty ones). This can aid decoding speed
                                depending on implementation but requires a bit
                                more space and encoding speed could be reduced
                                if getting length of any of the containers is
                                expensive.
        sort_keys (bool): Sort keys of dictionaries

    Raises:
        EncoderException: If an encoding failure occured.

    The following Python types and interfaces (ABCs) are supported (as are any
    subclasses):

    +------------------------------+-----------------------------------+
    | Python                       | UBJSON                            |
    +==============================+===================================+
    | (3) str                      | string                            |
    | (2) unicode                  |                                   |
    +------------------------------+-----------------------------------+
    | None                         | null                              |
    +------------------------------+-----------------------------------+
    | bool                         | true, false                       |
    +------------------------------+-----------------------------------+
    | (3) int                      | uint8, int8, int16, int32, int64, |
    | (2) int, long                | high_precision                    |
    +------------------------------+-----------------------------------+
    | float                        | float32, float64, high_precision  |
    +------------------------------+-----------------------------------+
    | Decimal                      | high_precision                    |
    +------------------------------+-----------------------------------+
    | (3) bytes, bytearray         | array (type, uint8)               |
    | (2) str                      | array (type, uint8)               |
    +------------------------------+-----------------------------------+
    | (3) collections.abc.Mapping  | object                            |
    | (2) collections.Mapping      |                                   |
    +------------------------------+-----------------------------------+
    | (3) collections.abc.Sequence | array                             |
    | (2) collections.Sequence     |                                   |
    +------------------------------+-----------------------------------+

    Notes:
    - Items are resolved in the order of this table, e.g. if the item implements
      both Mapping and Sequence interfaces, it will be encoded as a mapping.
    - None and bool do not use an isinstance check
    - Numbers in brackets denote Python version.
    - Only unicode strings in Python 2 are encoded as strings, i.e. for
      compatibility with e.g. Python 3 one MUST NOT use str in Python 2 (as that
      will be interpreted as a byte array).
    - Mapping keys have to be strings: str for Python3 and unicode or str in
      Python 2.
    """
    __dump(obj, fp.write, container_count=container_count, sort_keys=sort_keys)


def dumpb(obj, container_count=False, sort_keys=False):
    """Returns the given object as UBJSON in a bytes instance. See dump() for
       available arguments."""
    with BytesIO() as fp:
        __dump(obj, fp.write, container_count=container_count, sort_keys=sort_keys)
        return fp.getvalue()
