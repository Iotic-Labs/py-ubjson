# Copyright 2015 Iotic Labs Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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

__TYPES = frozenset((TYPE_NULL, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16, TYPE_INT32,
                     TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING))
__TYPES_NO_DATA = frozenset((TYPE_NULL, TYPE_BOOL_FALSE, TYPE_BOOL_TRUE))


class DecoderException(ValueError):
    """Raised when decoding of a UBJSON stream fails."""

    def __init__(self, message, fp=None):
        if fp is None:
            super(DecoderException, self).__init__(str(message))
        else:
            super(DecoderException, self).__init__('%s (at byte %d)' % (message, fp.tell()))


# pylint:disable=unused-argument
def __decode_high_prec(fp_read, marker):  # noqa (unused arg)
    length = __decode_int(fp_read, fp_read(1))
    if length > 0:
        raw = fp_read(length)
        if len(raw) < length:
            raise DecoderException('High prec. too short')
        try:
            return Decimal(raw.decode('utf-8'))
        except UnicodeError as ex:
            raise_from(DecoderException('Failed to decode decimal string'), ex)
        except DecimalException as ex:
            raise_from(DecoderException('Failed to decode decimal'), ex)


__INT_MAPPING = {TYPE_UINT8: (1, '>B'),
                 TYPE_INT8: (1, '>b'),
                 TYPE_INT16: (2, '>h'),
                 TYPE_INT32: (4, '>i'),
                 TYPE_INT64: (8, '>q')}


# pylint:disable=unused-argument
def __decode_int(fp_read, marker):  # noqa (unused arg)
    try:
        length, fmt = __INT_MAPPING[marker]
    except KeyError as ex:
        # Theoretically this could also be TYPE_HIGH_PREC but the the only time __decode_int is used (other than for
        # plain integers) is when dealing with strings, which shouldn't be able to fit something larger than 64-bit. Why
        # not an assert? Strings require length so the marker might not for an integer if input invalid.
        raise_from(DecoderException('Integer marker expected'), ex)
    else:
        try:
            return unpack(fmt, fp_read(length))[0]
        except StructError as ex:
            raise_from(DecoderException('Failed to unpack integer'), ex)


def __decode_float(fp_read, marker):
    if marker == TYPE_FLOAT32:
        try:
            return unpack('>f', fp_read(4))[0]
        except StructError as ex:
            raise_from(DecoderException('Failed to unpack float32'), ex)
    # TYPE_FLOAT64
    else:
        try:
            return unpack('>d', fp_read(8))[0]
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
    length = __decode_int(fp_read, fp_read(1))
    if length < 0:
        raise DecoderException('String length negative')
    raw = fp_read(length)
    if len(raw) < length:
        raise DecoderException('String too short')
    try:
        return raw.decode('utf-8')
    except UnicodeError as ex:
        raise_from(DecoderException('Failed to decode string'), ex)


# same as string, except there is no 'S' marker
def __decode_object_key(fp_read, marker):
    length = __decode_int(fp_read, marker)
    if length < 0:
        raise DecoderException('String length negative')
    raw = fp_read(length)
    if len(raw) < length:
        raise DecoderException('String too short')
    try:
        return raw.decode('utf-8')
    except UnicodeError as ex:
        raise_from(DecoderException('Failed to decode object key'), ex)


def __get_container_params(fp_read, in_mapping, no_bytes, object_pairs_hook):  # pylint: disable=too-many-branches
    container = object_pairs_hook() if in_mapping else []
    next_byte = fp_read(1)
    if next_byte == CONTAINER_TYPE:
        next_byte = fp_read(1)
        if next_byte not in __TYPES:
            raise DecoderException('Invalid container type')
        type_ = next_byte
        next_byte = fp_read(1)
    else:
        type_ = TYPE_NONE
    if next_byte == CONTAINER_COUNT:
        count = __decode_int(fp_read, fp_read(1))
        counting = True

        # special case - no data (None or bool)
        if type_ in __TYPES_NO_DATA:
            if in_mapping:
                value = __METHOD_MAP[type_](fp_read, type_)
                for _ in range(count):
                    container[__decode_object_key(fp_read, fp_read(1))] = value
            else:
                container = [__METHOD_MAP[type_](fp_read, type_)] * count
            next_byte = fp_read(1)
            # Make __decode_container finish immediately
            count = 0
        # special case - bytes array
        elif type_ == TYPE_UINT8 and not no_bytes:
            container = fp_read(count)
            if len(container) < count:
                raise DecoderException('Container bytes array too short')
            next_byte = fp_read(1)
            # Make __decode_container finish immediately
            count = 0
        else:
            # Reading ahead is just to capture type, which will not exist if type is fixed
            next_byte = fp_read(1) if (in_mapping or type_ == TYPE_NONE) else type_

    elif type_ == TYPE_NONE:
        # set to one to indicate that not finished yet
        count = 1
        counting = False
    else:
        raise DecoderException('Container type without count')
    return next_byte, counting, count, type_, container


__METHOD_MAP = {TYPE_NULL: (lambda _, __: None),
                TYPE_BOOL_TRUE: (lambda _, __: True),
                TYPE_BOOL_FALSE: (lambda _, __: False),
                TYPE_INT8: __decode_int,
                TYPE_UINT8: __decode_int,
                TYPE_INT16: __decode_int,
                TYPE_INT32: __decode_int,
                TYPE_INT64: __decode_int,
                TYPE_FLOAT32: __decode_float,
                TYPE_FLOAT64: __decode_float,
                TYPE_HIGH_PREC: __decode_high_prec,
                TYPE_CHAR: __decode_char,
                TYPE_STRING: __decode_string}


# pylint: disable=too-many-branches,too-many-locals
def __decode_container(fp_read, in_mapping, no_bytes, object_pairs_hook):  # noqa (complexity)
    """marker - start of container marker (for sanity checking only)
       container - what to add elements to"""
    marker, counting, count, type_, container = __get_container_params(fp_read, in_mapping, no_bytes, object_pairs_hook)
    # stack for keeping track of child-containers
    stack = deque()
    # key for current object
    key = value = None

    while True:
        # return to parsing parent container if end reached
        if count == 0 or (not counting and ((marker == OBJECT_END and in_mapping) or
                                            (marker == ARRAY_END and not in_mapping))):
            value = container
            try:
                # restore state in parent container
                old_in_mapping, old_counting, count, container, old_type_, key = stack.pop()
            except IndexError:
                # top-level container reached
                break
            else:
                # without count, must read next character (since current one is container-end)
                if not counting:
                    marker = fp_read(1) if (in_mapping or type_ == TYPE_NONE) else type_
                in_mapping, counting, type_ = old_in_mapping, old_counting, old_type_
        else:
            # decode key for object
            if in_mapping:
                key = __decode_object_key(fp_read, marker)
                marker = fp_read(1) if type_ == TYPE_NONE else type_

            # decode value
            try:
                value = __METHOD_MAP[marker](fp_read, marker)
            except KeyError:
                handled = False
            else:
                marker = fp_read(1) if (in_mapping or type_ == TYPE_NONE) else type_
                handled = True

            # handle outside above except (on KeyError) so do not have unfriendly "exception within except" backtrace
            if not handled:
                # Note: value will be added to parent container once parsed fully
                if marker == ARRAY_START:
                    stack.append((in_mapping, counting, count, container, type_, key))
                    in_mapping = False
                    marker, counting, count, type_, container = __get_container_params(fp_read, in_mapping, no_bytes,
                                                                                       object_pairs_hook)
                    continue
                elif marker == OBJECT_START:
                    stack.append((in_mapping, counting, count, container, type_, key))
                    in_mapping = True
                    marker, counting, count, type_, container = __get_container_params(fp_read, in_mapping, no_bytes,
                                                                                       object_pairs_hook)
                    continue
                else:
                    raise DecoderException('Invalid marker within %s' % ('object' if in_mapping else 'array'))

        # assign (key and) value now that they have been decoded fully
        if in_mapping:
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

    fp_read = fp.read
    marker = fp_read(1)
    try:
        try:
            return __METHOD_MAP[marker](fp_read, marker)
        except KeyError:
            pass
        if marker == ARRAY_START:
            return __decode_container(fp_read, False, bool(no_bytes), object_pairs_hook)
        elif marker == OBJECT_START:
            return __decode_container(fp_read, True, bool(no_bytes), object_pairs_hook)
        else:
            raise DecoderException('Invalid marker')
    except DecoderException as ex:
        raise_from(DecoderException(ex.args[0], fp), ex)


def loadb(chars, no_bytes=False, object_pairs_hook=None):
    """Decodes and returns UBJSON from the given bytes or bytesarray object. See
       load() for available arguments."""
    with BytesIO(chars) as fp:
        return load(fp, no_bytes=no_bytes, object_pairs_hook=object_pairs_hook)
