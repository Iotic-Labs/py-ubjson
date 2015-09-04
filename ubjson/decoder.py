# Copyright (c) 2015, Iotic Labs Ltd.
# All rights reserved.
# Licensed under 2-clause BSD license - see LICENSE file for details.

"""Non-resursive UBJSON decoder. It does NOT support No-Op ('N') values"""

from io import BytesIO
from collections import deque
from struct import unpack, error as StructError
from decimal import Decimal, DecimalException

from .compat import raise_from, Mapping
try:
    from .markers import (TYPE_NONE, TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16,
                          TYPE_INT32, TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING,
                          OBJECT_START, OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)
    # decoder.pxd defines these when C extension is enabled
except ImportError:  # pragma: no cover
    pass

__containerTypeStarts = frozenset((ARRAY_START, OBJECT_START))
__types = frozenset((TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32,
                     TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING))
__typesNoData = frozenset((TYPE_NULL, TYPE_BOOL_FALSE, TYPE_BOOL_TRUE))


class DecoderException(ValueError):
    """Raised when decoding of a UBJSON stream fails."""

    def __init__(self, message, fp=None):
        if fp is None:
            super(DecoderException, self).__init__(str(message))
        else:
            super(DecoderException, self).__init__('%s (at byte %d)' % (message, fp.tell()))


# pylint:disable=unused-argument
def __decodeHighPrec(fpRead, marker):  # noqa (unused arg)
    length = __decodeInt(fpRead, fpRead(1))
    if length > 0:
        raw = fpRead(length)
        if len(raw) < length:
            raise DecoderException('High prec. too short')
        try:
            return Decimal(raw.decode('utf-8'))
        except UnicodeError as e:
            raise_from(DecoderException('Failed to decode decimal string'), e)
        except DecimalException as e:
            raise_from(DecoderException('Failed to decode decimal'), e)


__intMapping = {TYPE_UINT8: (1, '>B'),
                TYPE_INT8: (1, '>b'),
                TYPE_INT16: (2, '>h'),
                TYPE_INT32: (4, '>i'),
                TYPE_INT64: (8, '>q')}


# pylint:disable=unused-argument
def __decodeInt(fpRead, marker):  # noqa (unused arg)
    try:
        length, fmt = __intMapping[marker]
    except KeyError as e:
        # Theoretically this could also be TYPE_HIGH_PREC but the the only time __decodeInt is used (other than for
        # plain integers) is when dealing with strings, which shouldn't be able to fit something larger than 64-bit. Why
        # not an assert? Strings require length so the marker might not for an integer if input invalid.
        raise_from(DecoderException('Integer marker expected'), e)
    else:
        try:
            return unpack(fmt, fpRead(length))[0]
        except StructError as e:
            raise_from(DecoderException('Failed to unpack integer'), e)


def __decodeFloat(fpRead, marker):
    if marker == TYPE_FLOAT32:
        try:
            return unpack('>f', fpRead(4))[0]
        except StructError as e:
            raise_from(DecoderException('Failed to unpack float32'), e)
    # TYPE_FLOAT64
    else:
        try:
            return unpack('>d', fpRead(8))[0]
        except StructError as e:
            raise_from(DecoderException('Failed to unpack float64'), e)


def __decodeChar(fpRead, marker):
    raw = fpRead(1)
    if not raw:
        raise DecoderException('Char missing')
    try:
        return raw.decode('utf-8')
    except UnicodeError as e:
        raise_from(DecoderException('Failed to decode char'), e)


def __decodeString(fpRead, marker):
    length = __decodeInt(fpRead, fpRead(1))
    if length < 0:
        raise DecoderException('String length negative')
    raw = fpRead(length)
    if len(raw) < length:
        raise DecoderException('String too short')
    try:
        return raw.decode('utf-8')
    except UnicodeError as e:
        raise_from(DecoderException('Failed to decode string'), e)


# same as string, except there is no 'S' marker
def __decodeObjectKey(fpRead, marker):
    length = __decodeInt(fpRead, marker)
    if length < 0:
        raise DecoderException('String length negative')
    raw = fpRead(length)
    if len(raw) < length:
        raise DecoderException('String too short')
    try:
        return raw.decode('utf-8')
    except UnicodeError as e:
        raise_from(DecoderException('Failed to decode object key'), e)


def __getContainerParams(fpRead, inMapping, noBytes, object_pairs_hook):  # pylint: disable=too-many-branches
    container = object_pairs_hook() if inMapping else []
    nextByte = fpRead(1)
    if nextByte == CONTAINER_TYPE:
        nextByte = fpRead(1)
        if nextByte not in __types:
            raise DecoderException('Invalid container type')
        type_ = nextByte
        nextByte = fpRead(1)
    else:
        type_ = TYPE_NONE
    if nextByte == CONTAINER_COUNT:
        count = __decodeInt(fpRead, fpRead(1))
        counting = True

        # special case - no data (None or bool)
        if type_ in __typesNoData:
            if inMapping:
                value = __methodMap[type_](fpRead, type_)
                for _ in range(count):
                    container[__decodeObjectKey(fpRead, fpRead(1))] = value
            else:
                container = [__methodMap[type_](fpRead, type_)] * count
            nextByte = fpRead(1)
            # Make __decodeContainer finish immediately
            count = 0
        # special case - bytes array
        elif type_ == TYPE_UINT8 and not noBytes:
            container = fpRead(count)
            if len(container) < count:
                raise DecoderException('Container bytes array too short')
            nextByte = fpRead(1)
            # Make __decodeContainer finish immediately
            count = 0
        else:
            # Reading ahead is just to capture type, which will not exist if type is fixed
            nextByte = fpRead(1) if (inMapping or type_ == TYPE_NONE) else type_

    elif type_ == TYPE_NONE:
        # set to one to indicate that not finished yet
        count = 1
        counting = False
    else:
        raise DecoderException('Container type without count')
    return nextByte, counting, count, type_, container


__methodMap = {TYPE_NULL: (lambda _, __: None),
               TYPE_BOOL_TRUE: (lambda _, __: True),
               TYPE_BOOL_FALSE: (lambda _, __: False),
               TYPE_INT8: __decodeInt,
               TYPE_UINT8: __decodeInt,
               TYPE_INT16: __decodeInt,
               TYPE_INT32: __decodeInt,
               TYPE_INT64: __decodeInt,
               TYPE_FLOAT32: __decodeFloat,
               TYPE_FLOAT64: __decodeFloat,
               TYPE_HIGH_PREC: __decodeHighPrec,
               TYPE_CHAR: __decodeChar,
               TYPE_STRING: __decodeString}


# pylint: disable=too-many-branches,too-many-locals
def __decodeContainer(fpRead, inMapping, noBytes, object_pairs_hook):  # noqa (complexity)
    """marker - start of container marker (for sanity checking only)
       container - what to add elements to"""
    marker, counting, count, type_, container = __getContainerParams(fpRead, inMapping, noBytes, object_pairs_hook)
    # stack for keeping track of child-containers
    stack = deque()
    # key for current object
    key = value = None

    while True:
        # return to parsing parent container if end reached
        if count == 0 or (not counting and ((marker == OBJECT_END and inMapping) or
                                            (marker == ARRAY_END and not inMapping))):
            value = container
            try:
                # restore state in parent container
                oldInMapping, oldCounting, count, container, oldType_, key = stack.pop()
            except IndexError:
                # top-level container reached
                break
            else:
                # without count, must read next character (since current one is container-end)
                if not counting:
                    marker = fpRead(1) if (inMapping or type_ == TYPE_NONE) else type_
                inMapping, counting, type_ = oldInMapping, oldCounting, oldType_
        else:
            # decode key for object
            if inMapping:
                key = __decodeObjectKey(fpRead, marker)
                marker = fpRead(1) if type_ == TYPE_NONE else type_

            # decode value
            try:
                value = __methodMap[marker](fpRead, marker)
            except KeyError:
                handled = False
            else:
                marker = fpRead(1) if (inMapping or type_ == TYPE_NONE) else type_
                handled = True

            # handle outside above except (on KeyError) so do not have unfriendly "exception within except" backtrace
            if not handled:
                # Note: value will be added to parent container once parsed fully
                if marker == ARRAY_START:
                    stack.append((inMapping, counting, count, container, type_, key))
                    inMapping = False
                    marker, counting, count, type_, container = __getContainerParams(fpRead, inMapping, noBytes,
                                                                                     object_pairs_hook)
                    continue
                elif marker == OBJECT_START:
                    stack.append((inMapping, counting, count, container, type_, key))
                    inMapping = True
                    marker, counting, count, type_, container = __getContainerParams(fpRead, inMapping, noBytes,
                                                                                     object_pairs_hook)
                    continue
                else:
                    raise DecoderException('Invalid marker within %s' % ('object' if inMapping else 'array'))

        # assign (key and) value now that they have been decoded fully
        if inMapping:
            container[key] = value
        else:
            container.append(value)
        if counting:
            count -= 1

    return container


def load(fp, no_bytes=False, object_pairs_hook=None):
    """Decodes and returns UBJSON from the given file-like object

    Args:
        fp: read([size])-able object
        no_bytes (bool): If set, typed UBJSON arrays (uint8) will not be
                         converted to a bytes instance and instead treated like
                         any other array (i.e. result in a list).
        object_pairs_hook (class): A alternative class to use as the mapping
                                   type (instead of dict), e.g. OrderedDict
                                   from the collections module.

    Returns:
        Decoded object

    Raises:
        DecoderException: If an encoding failure occured.

    UBJSON types are mapped to Python types as follows.  Numbers in brackets
    denote Python version.

        +----------------------------------+---------------+
        | UBJSON                           | Python        |
        +==================================+===============+
        | object                           | dict          |
        +----------------------------------+---------------+
        | array                            | list          |
        +----------------------------------+---------------+
        | string                           | (3) str       |
        |                                  | (2) unicode   |
        +----------------------------------+---------------+
        | uint8, int8, int16, int32, int64 | (3) int       |
        |                                  | (2) int, long |
        +----------------------------------+---------------+
        | float32, float64                 | float         |
        +----------------------------------+---------------+
        | high_precision                   | Decimal       |
        +----------------------------------+---------------+
        | array (typed, uint8)             | (3) bytes     |
        |                                  | (2) str       |
        +----------------------------------+---------------+
        | true                             | True          |
        +----------------------------------+---------------+
        | false                            | False         |
        +----------------------------------+---------------+
        | null                             | None          |
        +----------------------------------+---------------+
    """
    if object_pairs_hook is None:
        object_pairs_hook = dict
    elif not issubclass(object_pairs_hook, Mapping):
        raise TypeError('object_pairs_hook is not a mapping type')

    fpRead = fp.read
    marker = fpRead(1)
    try:
        try:
            return __methodMap[marker](fpRead, marker)
        except KeyError:
            pass
        if marker == ARRAY_START:
            return __decodeContainer(fpRead, False, bool(no_bytes), object_pairs_hook)
        elif marker == OBJECT_START:
            return __decodeContainer(fpRead, True, bool(no_bytes), object_pairs_hook)
        else:
            raise DecoderException('Invalid marker')
    except DecoderException as e:
        raise_from(DecoderException(e.args[0], fp), e)


def loadb(chars, no_bytes=False, object_pairs_hook=None):
    """Decodes and returns UBJSON from the given bytes or bytesarray object. See
       load() for available arguments."""
    with BytesIO(chars) as fp:
        return load(fp, no_bytes=no_bytes, object_pairs_hook=object_pairs_hook)
