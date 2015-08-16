# Copyright (c) 2015, V. Termanis, Iotic Labs Ltd.
# All rights reserved. See LICENSE document for details.

"""Non-resursive UBJSON encoder"""

from collections import deque
from struct import pack
from decimal import Decimal
from io import BytesIO

from .compat import Mapping, Sequence, integer_types, string_types
from .markers import (TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32,
                      TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING, OBJECT_START,
                      OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)

__byteTypes = (bytes, bytearray)


class EncoderException(TypeError):
    """Raised when encoding of an object fails."""
    pass


def __encodeHighPrec(fp, item):
    fp.write(TYPE_HIGH_PREC)
    encodedVal = str(Decimal(item)).encode('utf-8')
    __encodeInt(fp, len(encodedVal))
    fp.write(encodedVal)


def __encodeDecimal(fp, item):
    fp.write(TYPE_HIGH_PREC)
    encodedVal = str(item).encode('utf-8')
    __encodeInt(fp, len(encodedVal))
    fp.write(encodedVal)


def __encodeInt(fp, item):
    if item >= 0:
        if item <= 255:
            fp.write(TYPE_UINT8)
            fp.write(pack('>B', item))
        elif item <= 32767:
            fp.write(TYPE_INT16)
            fp.write(pack('>h', item))
        elif item <= 2147483647:
            fp.write(TYPE_INT32)
            fp.write(pack('>i', item))
        elif item <= 9223372036854775807:
            fp.write(TYPE_INT64)
            fp.write(pack('>q', item))
        else:
            __encodeHighPrec(fp, item)
    elif item >= -128:
        fp.write(TYPE_INT8)
        fp.write(pack('>b', item))
    elif item >= -32768:
        fp.write(TYPE_INT16)
        fp.write(pack('>h', item))
    elif item >= -2147483648:
        fp.write(TYPE_INT32)
        fp.write(pack('>i', item))
    elif item >= -9223372036854775808:
        fp.write(TYPE_INT64)
        fp.write(pack('>q', item))
    else:
        __encodeHighPrec(fp, item)


def __encodeFloat(fp, item):
    if 1.18e-38 <= abs(item) <= 3.4e38 or item == 0:
        fp.write(TYPE_FLOAT32)
        fp.write(pack('>f', item))
    elif 2.23e-308 <= abs(item) < 1.8e308:
        fp.write(TYPE_FLOAT64)
        fp.write(pack('>d', item))
    else:
        __encodeHighPrec(fp, item)


def __encodeString(fp, item):
    encodedVal = item.encode('utf-8')
    length = len(encodedVal)
    if length == 1:
        fp.write(TYPE_CHAR)
    else:
        fp.write(TYPE_STRING)
        if length <= 255:
            fp.write(TYPE_UINT8)
            fp.write(pack('>B', length))
        elif length <= 32767:
            fp.write(TYPE_INT16)
            fp.write(pack('>h', length))
        elif length <= 2147483647:  # pragma: no cover
            fp.write(TYPE_INT32)
            fp.write(pack('>i', length))
        elif length <= 9223372036854775807:  # pragma: no cover
            fp.write(TYPE_INT64)
            fp.write(pack('>q', length))
        else:  # pragma: no cover
            __encodeHighPrec(fp, length)
    fp.write(encodedVal)


# similar to encodeString, except 'S' marker is not added
def __encodeObjectKey(fp, key):
    encodedVal = key.encode('utf-8')
    length = len(encodedVal)
    if length <= 255:
        fp.write(TYPE_UINT8)
        fp.write(pack('>B', length))
    elif length <= 32767:
        fp.write(TYPE_INT16)
        fp.write(pack('>h', length))
    elif length <= 2147483647:
        fp.write(TYPE_INT32)
        fp.write(pack('>i', length))
    elif length <= 9223372036854775807:  # pragma: no cover
        fp.write(TYPE_INT64)
        fp.write(pack('>q', length))
    else:  # pragma: no cover
        __encodeHighPrec(fp, length)
    fp.write(encodedVal)


def __encodeBytes(fp, item):
    fp.write(ARRAY_START)
    fp.write(CONTAINER_TYPE)
    fp.write(TYPE_UINT8)
    fp.write(CONTAINER_COUNT)
    __encodeInt(fp, len(item))
    fp.write(item)
    # no ARRAY_END since length was specified


# pylint: disable=too-many-branches,too-many-statements
def __encodeContainer(fp, obj, inMapping, seenContainers, containerCount, sort_keys):  # noqa (complexity)
    """Performs encoding within an array or object"""
    # stack for keeping track of sequences and mappings without requiring recursion
    stack = deque()
    # current object being encoded
    current = obj
    # child container id() used to avoid circular references
    containerId = None

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
                        fp.write(OBJECT_END)
                    # for circular reference checking
                    if containerId is not None:
                        del seenContainers[containerId]
                    continue
            if isinstance(key, string_types):
                __encodeObjectKey(fp, key)
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
                        fp.write(ARRAY_END)
                    # for circular reference checking
                    if containerId is not None:
                        del seenContainers[containerId]
                    continue

        # encode value
        if isinstance(item, string_types):
            __encodeString(fp, item)

        elif item is None:
            fp.write(TYPE_NULL)

        elif item is True:
            fp.write(TYPE_BOOL_TRUE)

        elif item is False:
            fp.write(TYPE_BOOL_FALSE)

        elif isinstance(item, int):
            __encodeInt(fp, item)

        elif isinstance(item, float):
            __encodeFloat(fp, item)

        elif isinstance(item, Decimal):
            __encodeDecimal(fp, item)

        elif isinstance(item, __byteTypes):
            __encodeBytes(fp, item)

        # order important since mappings could also be sequences
        elif isinstance(item, Mapping):
            # circular reference check
            containerId = id(item)
            if containerId in seenContainers:
                raise EncoderException('Circular reference detected')
            seenContainers[containerId] = item

            fp.write(OBJECT_START)
            if containerCount:
                fp.write(CONTAINER_COUNT)
                __encodeInt(fp, len(item))
            stack.append((inMapping, current, containerId))
            current = iter(sorted(item.items()) if sort_keys else item.items())
            inMapping = True

        elif isinstance(item, Sequence):
            # circular reference check
            containerId = id(item)
            if containerId in seenContainers:
                raise EncoderException('Circular reference detected')
            seenContainers[containerId] = item

            fp.write(ARRAY_START)
            if containerCount:
                fp.write(CONTAINER_COUNT)
                __encodeInt(fp, len(item))
            stack.append((inMapping, current, containerId))
            current = iter(item)
            inMapping = False

        else:
            raise EncoderException(fp, 'Cannot encode item of type %s' % type(item))


def dump(obj, fp, container_count=False, sort_keys=False):  # noqa (complexity)
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
    Returns:
        bytes: Encoded UBJSON

    Raises:
        EncoderException: If an encoding failure occured.

    The following Python types and interfaces (ABCs) are supported (as are any
    subclasses). Note that items are resolved in the order of this table, e.g.
    if the item implements both Mapping and Sequence interfaces, it will be
    encoded as a mapping. Also note that None and bool do not use an instance
    check.

        +-------------------+---------------------------------------------------+
        | Python            | UBJSON                                            |
        +===================+===================================================+
        | str               | string                                            |
        +-------------------+---------------------------------------------------+
        | None              | null                                              |
        +-------------------+---------------------------------------------------+
        | bool              | true, false                                       |
        +-------------------+---------------------------------------------------+
        | int               | uint8, int8, int16, int32, int64, high_precision  |
        +-------------------+---------------------------------------------------+
        | float             | float32, float64, high_precision                  |
        +-------------------+---------------------------------------------------+
        | Decimal           | high_precision                                    |
        +-------------------+---------------------------------------------------+
        | bytes, bytearray  | array (type, uint8)                               |
        +-------------------+---------------------------------------------------+
        | abc.Mapping       | object                                            |
        +-------------------+---------------------------------------------------+
        | abc.Sequence      | array                                             |
        +-------------------+---------------------------------------------------+
    """
    if isinstance(obj, string_types):
        __encodeString(fp, obj)

    elif obj is None:
        fp.write(TYPE_NULL)

    elif obj is True:
        fp.write(TYPE_BOOL_TRUE)

    elif obj is False:
        fp.write(TYPE_BOOL_FALSE)

    elif isinstance(obj, integer_types):
        __encodeInt(fp, obj)

    elif isinstance(obj, float):
        __encodeFloat(fp, obj)

    elif isinstance(obj, Decimal):
        __encodeDecimal(fp, obj)

    elif isinstance(obj, __byteTypes):
        __encodeBytes(fp, obj)

    # order important since mappings could also be sequences
    elif isinstance(obj, Mapping):
        fp.write(OBJECT_START)
        if container_count:
            fp.write(CONTAINER_COUNT)
            __encodeInt(fp, len(obj))
        __encodeContainer(fp, iter(sorted(obj.items()) if sort_keys else obj.items()), True, {id(obj): obj},
                          container_count, sort_keys)
        if not container_count:
            fp.write(OBJECT_END)

    elif isinstance(obj, Sequence):
        fp.write(ARRAY_START)
        if container_count:
            fp.write(CONTAINER_COUNT)
            __encodeInt(fp, len(obj))
        __encodeContainer(fp, iter(obj), False, {id(obj): obj}, container_count, sort_keys)
        if not container_count:
            fp.write(ARRAY_END)

    else:
        raise EncoderException(fp, 'Cannot encode item of type %s' % type(obj))


def dumpb(obj, container_count=False, sort_keys=False):
    """Returns the given object as UBJSON in a bytes instance. See dump() for
       available arguments."""
    with BytesIO() as fp:
        dump(obj, fp, container_count=container_count, sort_keys=sort_keys)
        return fp.getvalue()
