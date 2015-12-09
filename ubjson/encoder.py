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


"""Non-resursive UBJSON encoder"""

from collections import deque
from struct import pack
from decimal import Decimal
from io import BytesIO

from .compat import Mapping, Sequence, INTEGER_TYPES, UNICODE_TYPE, TEXT_TYPES, BYTES_TYPES
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


def __encode_high_prec(fp_write, item):
    fp_write(TYPE_HIGH_PREC)
    encoded_val = str(Decimal(item)).encode('utf-8')
    __encode_int(fp_write, len(encoded_val))
    fp_write(encoded_val)


def __encode_decimal(fp_write, item):
    fp_write(TYPE_HIGH_PREC)
    encoded_val = str(item).encode('utf-8')
    __encode_int(fp_write, len(encoded_val))
    fp_write(encoded_val)


def __encode_int(fp_write, item):
    if item >= 0:
        if item <= 255:
            fp_write(TYPE_UINT8)
            fp_write(pack('>B', item))
        elif item <= 32767:
            fp_write(TYPE_INT16)
            fp_write(pack('>h', item))
        elif item <= 2147483647:
            fp_write(TYPE_INT32)
            fp_write(pack('>i', item))
        elif item <= 9223372036854775807:
            fp_write(TYPE_INT64)
            fp_write(pack('>q', item))
        else:
            __encode_high_prec(fp_write, item)
    elif item >= -128:
        fp_write(TYPE_INT8)
        fp_write(pack('>b', item))
    elif item >= -32768:
        fp_write(TYPE_INT16)
        fp_write(pack('>h', item))
    elif item >= -2147483648:
        fp_write(TYPE_INT32)
        fp_write(pack('>i', item))
    elif item >= -9223372036854775808:
        fp_write(TYPE_INT64)
        fp_write(pack('>q', item))
    else:
        __encode_high_prec(fp_write, item)


def __encode_float(fp_write, item):
    if 1.18e-38 <= abs(item) <= 3.4e38 or item == 0:
        fp_write(TYPE_FLOAT32)
        fp_write(pack('>f', item))
    elif 2.23e-308 <= abs(item) < 1.8e308:
        fp_write(TYPE_FLOAT64)
        fp_write(pack('>d', item))
    else:
        __encode_high_prec(fp_write, item)


def __encode_string(fp_write, item):
    encoded_val = item.encode('utf-8')
    length = len(encoded_val)
    if length == 1:
        fp_write(TYPE_CHAR)
    else:
        fp_write(TYPE_STRING)
        __encode_int(fp_write, length)
    fp_write(encoded_val)


# similar to encode_string, except 'S' marker is not added
def __encode_object_key(fp_write, key):
    encoded_val = key.encode('utf-8') if isinstance(key, UNICODE_TYPE) else key
    __encode_int(fp_write, len(encoded_val))
    fp_write(encoded_val)


def __encode_bytes(fp_write, item):
    fp_write(ARRAY_START)
    fp_write(CONTAINER_TYPE)
    fp_write(TYPE_UINT8)
    fp_write(CONTAINER_COUNT)
    __encode_int(fp_write, len(item))
    fp_write(item)
    # no ARRAY_END since length was specified


def __encode_value(fp_write, item):
    if isinstance(item, UNICODE_TYPE):
        __encode_string(fp_write, item)

    elif item is None:
        fp_write(TYPE_NULL)

    elif item is True:
        fp_write(TYPE_BOOL_TRUE)

    elif item is False:
        fp_write(TYPE_BOOL_FALSE)

    elif isinstance(item, INTEGER_TYPES):
        __encode_int(fp_write, item)

    elif isinstance(item, float):
        __encode_float(fp_write, item)

    elif isinstance(item, Decimal):
        __encode_decimal(fp_write, item)

    elif isinstance(item, BYTES_TYPES):
        __encode_bytes(fp_write, item)

    else:
        return False

    return True


# pylint: disable=too-many-branches,too-many-statements
def __encode_container(fp_write, obj, in_mapping, seen_containers, container_count, sort_keys):  # noqa (complexity)
    """Performs encoding within an array or object"""
    # stack for keeping track of sequences and mappings without requiring recursion
    stack = deque()
    # current object being encoded
    current = obj
    container_id = 0

    while True:
        # Get next item from container (or finish container and return to parent)
        if in_mapping:
            try:
                key, item = next(current)
            except StopIteration:
                try:
                    in_mapping, current, container_id = stack.pop()
                except IndexError:
                    # top-level container reached
                    break
                else:
                    if not container_count:
                        fp_write(OBJECT_END)
                    # for circular reference checking
                    del seen_containers[container_id]
                    continue
            # allow both str & unicode for Python 2
            if isinstance(key, TEXT_TYPES):
                __encode_object_key(fp_write, key)
            else:
                raise EncoderException('Mapping keys can only be strings')
        else:
            # sequence
            try:
                item = next(current)
            except StopIteration:
                try:
                    in_mapping, current, container_id = stack.pop()
                except IndexError:
                    # top-level container reached
                    break
                else:
                    if not container_count:
                        fp_write(ARRAY_END)
                    # for circular reference checking
                    del seen_containers[container_id]
                    continue

        if not __encode_value(fp_write, item):
            # order important since mappings could also be sequences
            if isinstance(item, Mapping):
                # circular reference check
                container_id = id(item)
                if container_id in seen_containers:
                    raise EncoderException('Circular reference detected')
                seen_containers[container_id] = item

                fp_write(OBJECT_START)
                if container_count:
                    fp_write(CONTAINER_COUNT)
                    __encode_int(fp_write, len(item))
                stack.append((in_mapping, current, container_id))
                current = iter(sorted(item.items()) if sort_keys else item.items())
                in_mapping = True

            elif isinstance(item, Sequence):
                # circular reference check
                container_id = id(item)
                if container_id in seen_containers:
                    raise EncoderException('Circular reference detected')
                seen_containers[container_id] = item

                fp_write(ARRAY_START)
                if container_count:
                    fp_write(CONTAINER_COUNT)
                    __encode_int(fp_write, len(item))
                stack.append((in_mapping, current, container_id))
                current = iter(item)
                in_mapping = False

            else:
                raise EncoderException('Cannot encode item of type %s' % type(item))


def __dump(obj, fp_write, container_count, sort_keys):  # noqa (complexity)
    if not __encode_value(fp_write, obj):
        # order important since mappings could also be sequences
        if isinstance(obj, Mapping):
            fp_write(OBJECT_START)
            if container_count:
                fp_write(CONTAINER_COUNT)
                __encode_int(fp_write, len(obj))
            __encode_container(fp_write, iter(sorted(obj.items()) if sort_keys else obj.items()), True, {id(obj): obj},
                               container_count, sort_keys)
            if not container_count:
                fp_write(OBJECT_END)

        elif isinstance(obj, Sequence):
            fp_write(ARRAY_START)
            if container_count:
                fp_write(CONTAINER_COUNT)
                __encode_int(fp_write, len(obj))
            __encode_container(fp_write, iter(obj), False, {id(obj): obj}, container_count, sort_keys)
            if not container_count:
                fp_write(ARRAY_END)

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
