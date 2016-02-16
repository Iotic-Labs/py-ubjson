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


"""UBJSON draft v12 decoder. It does NOT support No-Op ('N') values"""

from io import BytesIO
from struct import Struct, pack, error as StructError
from decimal import Decimal, DecimalException

from .compat import raise_from, Mapping
try:
    from .markers import (TYPE_NONE, TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16,
                          TYPE_INT32, TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING,
                          OBJECT_START, OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)
    # decoder.pxd defines these when C extension is enabled
except ImportError:  # pragma: no cover
    pass

__TYPES = frozenset((TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32,
                     TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING))
__TYPES_NO_DATA = frozenset((TYPE_NULL, TYPE_BOOL_FALSE, TYPE_BOOL_TRUE))
__TYPES_INT = frozenset((TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32, TYPE_INT64))

__SMALL_INTS_DECODED = {pack('>b', i): i for i in range(-128, 128)}
__SMALL_UINTS_DECODED = {pack('>B', i): i for i in range(256)}
__UNPACK_INT16 = Struct('>h').unpack
__UNPACK_INT32 = Struct('>i').unpack
__UNPACK_INT64 = Struct('>q').unpack
__UNPACK_FLOAT32 = Struct('>f').unpack
__UNPACK_FLOAT64 = Struct('>d').unpack


class DecoderException(ValueError):
    """Raised when decoding of a UBJSON stream fails."""

    def __init__(self, message, fp=None):
        if fp is None:
            super(DecoderException, self).__init__(str(message))
        else:
            super(DecoderException, self).__init__('%s (at byte %d)' % (message, fp.tell()))


# pylint: disable=unused-argument
def __decode_high_prec(fp_read, marker):
    length = __decode_int_non_negative(fp_read, fp_read(1))
    raw = fp_read(length)
    if len(raw) < length:
        raise DecoderException('High prec. too short')
    try:
        return Decimal(raw.decode('utf-8'))
    except UnicodeError as ex:
        raise_from(DecoderException('Failed to decode decimal string'), ex)
    except DecimalException as ex:
        raise_from(DecoderException('Failed to decode decimal'), ex)


def __decode_int_non_negative(fp_read, marker):
    if marker not in __TYPES_INT:
        raise DecoderException('Integer marker expected')
    value = __METHOD_MAP[marker](fp_read, marker)
    if value < 0:
        raise DecoderException('Negative count/length unexpected')
    return value


def __decode_int8(fp_read, marker):
    try:
        return __SMALL_INTS_DECODED[fp_read(1)]
    except KeyError as ex:
        raise_from(DecoderException('Failed to unpack int8'), ex)


def __decode_uint8(fp_read, marker):
    try:
        return __SMALL_UINTS_DECODED[fp_read(1)]
    except KeyError as ex:
        raise_from(DecoderException('Failed to unpack uint8'), ex)


def __decode_int16(fp_read, marker):
    try:
        return __UNPACK_INT16(fp_read(2))[0]
    except StructError as ex:
        raise_from(DecoderException('Failed to unpack int16'), ex)


def __decode_int32(fp_read, marker):
    try:
        return __UNPACK_INT32(fp_read(4))[0]
    except StructError as ex:
        raise_from(DecoderException('Failed to unpack int32'), ex)


def __decode_int64(fp_read, marker):
    try:
        return __UNPACK_INT64(fp_read(8))[0]
    except StructError as ex:
        raise_from(DecoderException('Failed to unpack int64'), ex)


def __decode_float32(fp_read, marker):
    try:
        return __UNPACK_FLOAT32(fp_read(4))[0]
    except StructError as ex:
        raise_from(DecoderException('Failed to unpack float32'), ex)


def __decode_float64(fp_read, marker):
    try:
        return __UNPACK_FLOAT64(fp_read(8))[0]
    except StructError as ex:
        raise_from(DecoderException('Failed to unpack float64'), ex)


def __decode_char(fp_read, marker):
    raw = fp_read(1)
    if not raw:
        raise DecoderException('Char missing')
    try:
        return raw.decode('utf-8')
    except UnicodeError as ex:
        raise_from(DecoderException('Failed to decode char'), ex)


def __decode_string(fp_read, marker):
    # current marker is string identifier, so read next byte which identifies integer type
    length = __decode_int_non_negative(fp_read, fp_read(1))
    raw = fp_read(length)
    if len(raw) < length:
        raise DecoderException('String too short')
    try:
        return raw.decode('utf-8')
    except UnicodeError as ex:
        raise_from(DecoderException('Failed to decode string'), ex)


# same as string, except there is no 'S' marker
def __decode_object_key(fp_read, marker):
    length = __decode_int_non_negative(fp_read, marker)
    raw = fp_read(length)
    if len(raw) < length:
        raise DecoderException('String too short')
    try:
        return raw.decode('utf-8')
    except UnicodeError as ex:
        raise_from(DecoderException('Failed to decode object key'), ex)


__METHOD_MAP = {TYPE_NULL: (lambda _, __: None),
                TYPE_BOOL_TRUE: (lambda _, __: True),
                TYPE_BOOL_FALSE: (lambda _, __: False),
                TYPE_INT8: __decode_int8,
                TYPE_UINT8: __decode_uint8,
                TYPE_INT16: __decode_int16,
                TYPE_INT32: __decode_int32,
                TYPE_INT64: __decode_int64,
                TYPE_FLOAT32: __decode_float32,
                TYPE_FLOAT64: __decode_float64,
                TYPE_HIGH_PREC: __decode_high_prec,
                TYPE_CHAR: __decode_char,
                TYPE_STRING: __decode_string}


def __get_container_params(fp_read, in_mapping, no_bytes, object_pairs_hook):  # pylint: disable=too-many-branches
    container = object_pairs_hook() if in_mapping else []
    marker = fp_read(1)
    if marker == CONTAINER_TYPE:
        marker = fp_read(1)
        if marker not in __TYPES:
            raise DecoderException('Invalid container type')
        type_ = marker
        marker = fp_read(1)
    else:
        type_ = TYPE_NONE
    if marker == CONTAINER_COUNT:
        count = __decode_int_non_negative(fp_read, fp_read(1))
        counting = True

        # special case - no data (None or bool)
        if type_ in __TYPES_NO_DATA:
            if in_mapping:
                value = __METHOD_MAP[type_](fp_read, type_)
                for _ in range(count):
                    container[__decode_object_key(fp_read, fp_read(1))] = value
            else:
                container = [__METHOD_MAP[type_](fp_read, type_)] * count
            # Make __decode_container finish immediately
            count = 0
        # special case - bytes array
        elif type_ == TYPE_UINT8 and not in_mapping and not no_bytes:
            container = fp_read(count)
            if len(container) < count:
                raise DecoderException('Container bytes array too short')
            # Make __decode_container finish immediately
            count = 0
        else:
            # Reading ahead is just to capture type, which will not exist if type is fixed
            marker = fp_read(1) if (in_mapping or type_ == TYPE_NONE) else type_

    elif type_ == TYPE_NONE:
        # set to one to indicate that not finished yet
        count = 1
        counting = False
    else:
        raise DecoderException('Container type without count')
    return marker, counting, count, type_, container


def __decode_object(fp_read, no_bytes, object_pairs_hook):
    marker, counting, count, type_, container = __get_container_params(fp_read, True, no_bytes, object_pairs_hook)
    value = None

    while count > 0 and (counting or marker != OBJECT_END):
        # decode key for object
        key = __decode_object_key(fp_read, marker)
        marker = fp_read(1) if type_ == TYPE_NONE else type_

        # decode value
        try:
            value = __METHOD_MAP[marker](fp_read, marker)
        except KeyError:
            handled = False
        else:
            handled = True

        # handle outside above except (on KeyError) so do not have unfriendly "exception within except" backtrace
        if not handled:
            if marker == ARRAY_START:
                value = __decode_array(fp_read, no_bytes, object_pairs_hook)
            elif marker == OBJECT_START:
                value = __decode_object(fp_read, no_bytes, object_pairs_hook)
            else:
                raise DecoderException('Invalid marker within object')

        container[key] = value
        if counting:
            count -= 1
        if count:
            marker = fp_read(1)

    return container


def __decode_array(fp_read, no_bytes, object_pairs_hook):
    marker, counting, count, type_, container = __get_container_params(fp_read, False, no_bytes, object_pairs_hook)
    value = None

    while count > 0 and (counting or marker != ARRAY_END):
        # decode value
        try:
            value = __METHOD_MAP[marker](fp_read, marker)
        except KeyError:
            handled = False
        else:
            handled = True

        # handle outside above except (on KeyError) so do not have unfriendly "exception within except" backtrace
        if not handled:
            if marker == ARRAY_START:
                value = __decode_array(fp_read, no_bytes, object_pairs_hook)
            elif marker == OBJECT_START:
                value = __decode_object(fp_read, no_bytes, object_pairs_hook)
            else:
                raise DecoderException('Invalid marker within array')

        container.append(value)
        if counting:
            count -= 1
        if count:
            marker = fp_read(1) if type_ == TYPE_NONE else type_

    return container


def load(fp, no_bytes=False, object_pairs_hook=None):  # noqa (complexity)
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

    if fp is None:
        raise TypeError('fp')
    if not callable(fp.read):
        raise TypeError('fp.read not callable')
    fp_read = fp.read

    marker = fp_read(1)
    try:
        try:
            return __METHOD_MAP[marker](fp_read, marker)
        except KeyError:
            pass
        if marker == ARRAY_START:
            return __decode_array(fp_read, bool(no_bytes), object_pairs_hook)
        elif marker == OBJECT_START:
            return __decode_object(fp_read, bool(no_bytes), object_pairs_hook)
        else:
            raise DecoderException('Invalid marker')
    except DecoderException as ex:
        raise_from(DecoderException(ex.args[0], fp), ex)


def loadb(chars, no_bytes=False, object_pairs_hook=None):
    """Decodes and returns UBJSON from the given bytes or bytesarray object. See
       load() for available arguments."""
    with BytesIO(chars) as fp:
        return load(fp, no_bytes=no_bytes, object_pairs_hook=object_pairs_hook)
