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


from sys import version_info
from io import BytesIO
from unittest import TestCase
from pprint import pformat
from decimal import Decimal
from struct import pack
from collections import OrderedDict

from ubjson import dump as ubjdump, dumpb as ubjdumpb, loadb as ubjloadb, EncoderException, DecoderException

# Not imported from ubjson.markers since cannot access them directly if compiled with cython

# Value types
TYPE_NONE = b'\x00'
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

PY2 = version_info[0] < 3

if PY2:
    def u(obj):
        """Casts obj to unicode string, unless already one"""
        return obj if isinstance(obj, unicode) else unicode(obj)  # noqa  pylint: disable=undefined-variable
else:
    def u(obj):
        """Casts obj to unicode string, unless already one"""
        return obj if isinstance(obj, str) else str(obj)


class TestEncodeDecode(TestCase):  # pylint: disable=too-many-public-methods

    @staticmethod
    def __format_in_out(obj, encoded):
        return '\nInput:\n%s\nOutput (%d):\n%s' % (pformat(obj), len(encoded), encoded)

    if PY2:  # pragma: no cover
        def type_check(self, actual, expected):
            self.assertEqual(actual, expected)
    else:  # pragma: no cover
        def type_check(self, actual, expected):
            self.assertEqual(actual, ord(expected))

    # based on math.isclose available in Python v3.5
    @staticmethod
    # pylint: disable=invalid-name
    def numbers_close(a, b, rel_tol=1e-05, abs_tol=0.0):
        return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)

    def check_enc_dec(self, obj,
                      # total length of encoded object
                      length=None,
                      # total length is at least the given number of bytes
                      length_greater_or_equal=False,
                      # approximate comparison (e.g. for float)
                      approximate=False,
                      # type marker expected at start of encoded output
                      expected_type=None,
                      # additional arguments to pass to encoder
                      **kwargs):
        """Black-box test to check whether the provided object is the same once encoded and subsequently decoded."""
        encoded = ubjdumpb(obj, **kwargs)
        if expected_type is not None:
            self.type_check(encoded[0], expected_type)
        if length is not None:
            assert_func = self.assertGreaterEqual if length_greater_or_equal else self.assertEqual
            assert_func(len(encoded), length, self.__format_in_out(obj, encoded))
        if approximate:
            self.assertTrue(self.numbers_close(ubjloadb(encoded), obj), msg=self.__format_in_out(obj, encoded))
        else:
            self.assertEqual(ubjloadb(encoded), obj, self.__format_in_out(obj, encoded))

    def test_no_data(self):
        with self.assertRaises(DecoderException):
            ubjloadb(b'')

    def test_trailing_input(self):
        self.assertEqual(ubjloadb(TYPE_BOOL_TRUE * 10), True)

    def test_invalid_marker(self):
        with self.assertRaises(DecoderException):
            ubjloadb(b'A')

    def test_bool(self):
        self.assertEqual(ubjdumpb(True), TYPE_BOOL_TRUE)
        self.assertEqual(ubjdumpb(False), TYPE_BOOL_FALSE)
        self.check_enc_dec(True, 1)
        self.check_enc_dec(False, 1)

    def test_null(self):
        self.assertEqual(ubjdumpb(None), TYPE_NULL)
        self.check_enc_dec(None, 1)

    def test_char(self):
        self.assertEqual(ubjdumpb(u('a')), TYPE_CHAR + 'a'.encode('utf-8'))
        # no char, char invalid utf-8
        for suffix in (b'', b'\xfe'):
            with self.assertRaises(DecoderException):
                ubjloadb(TYPE_CHAR + suffix)
        for char in (u('a'), u('\0'), u('~')):
            self.check_enc_dec(char, 2)

    def test_string(self):
        self.assertEqual(ubjdumpb(u('ab')), TYPE_STRING + TYPE_UINT8 + b'\x02' + 'ab'.encode('utf-8'))
        self.check_enc_dec(u(''), 3)
        # invalid string size, string too short, string invalid utf-8
        for suffix in (b'\x81', b'\x01', b'\x01' + b'\xfe'):
            with self.assertRaises(DecoderException):
                ubjloadb(TYPE_STRING + TYPE_INT8 + suffix)
        # Note: In Python 2 plain str type is encoded as byte array
        for string in ('some ascii', u(r'\u00a9 with extended\u2122'), u('long string') * 100):
            self.check_enc_dec(string, 4, length_greater_or_equal=True)

    def test_int(self):
        self.assertEqual(ubjdumpb(Decimal(-1.5)),
                         TYPE_HIGH_PREC + TYPE_UINT8 + b'\x04' + '-1.5'.encode('utf-8'))
        # insufficient length
        with self.assertRaises(DecoderException):
            ubjloadb(TYPE_INT16 + b'\x01')

        for type_, value, total_size in (
                (TYPE_UINT8, 0, 2),
                (TYPE_UINT8, 255, 2),
                (TYPE_INT8, -128, 2),
                (TYPE_INT16, -32768, 3),
                (TYPE_INT16, 32767, 3),
                (TYPE_INT32, 2147483647, 5),
                (TYPE_INT32, -2147483648, 5),
                (TYPE_INT64, 9223372036854775807, 9),
                (TYPE_INT64, -9223372036854775808, 9),
                # HIGH_PREC (marker + length marker + length + value)
                (TYPE_HIGH_PREC, 9223372036854775808, 22),
                (TYPE_HIGH_PREC, -9223372036854775809, 23),
                (TYPE_HIGH_PREC, 9999999999999999999999999999999999999, 40)):
            self.check_enc_dec(value, total_size, expected_type=type_)

    def test_high_precision(self):
        self.assertEqual(ubjdumpb(Decimal(-1.5)),
                         TYPE_HIGH_PREC + TYPE_UINT8 + b'\x04' + '-1.5'.encode('utf-8'))
        # insufficient length, invalid utf-8, invalid decimal value
        for suffix in (b'n', b'\xfe\xfe', b'na'):
            with self.assertRaises(DecoderException):
                ubjloadb(TYPE_HIGH_PREC + TYPE_UINT8 + b'\x02' + suffix)

        self.check_enc_dec('1.8e315')
        for value in (
                '0.0',
                '2.5',
                '10e30',
                '-1.2345e67890'):
            # minimum length because: marker + length marker + length + value
            self.check_enc_dec(Decimal(value), 4, length_greater_or_equal=True)
        # cannot compare equality, so test separately (since these evaluate to "NULL"
        for value in ('nan', '-inf', 'inf'):
            self.assertEqual(ubjloadb(ubjdumpb(Decimal(value))), None)

    def test_float(self):
        # insufficient length
        for float_type in (TYPE_FLOAT32, TYPE_FLOAT64):
            with self.assertRaises(DecoderException):
                ubjloadb(float_type + b'\x01')

        self.check_enc_dec(0.0, 5, expected_type=TYPE_FLOAT32)

        for type_, value, total_size in (
                (TYPE_FLOAT32, 1.18e-38, 5),
                (TYPE_FLOAT32, 3.4e38, 5),
                (TYPE_FLOAT64, 2.23e-308, 9),
                (TYPE_FLOAT64, 12345.44e40, 9),
                (TYPE_FLOAT64, 1.8e307, 9)):
            self.check_enc_dec(value,
                               total_size,
                               approximate=True,
                               expected_type=type_,
                               no_float32=False)
            # using only float64 (default)
            self.check_enc_dec(value,
                               9 if type_ == TYPE_FLOAT32 else total_size,
                               approximate=True,
                               expected_type=(TYPE_FLOAT64 if type_ == TYPE_FLOAT32 else type_))
        for value in ('nan', '-inf', 'inf'):
            for no_float32 in (True, False):
                self.assertEqual(ubjloadb(ubjdumpb(float(value), no_float32=no_float32)), None)
        # value which results in high_prec usage
        for no_float32 in (True, False):
            self.check_enc_dec(2.22e-308, 4, expected_type=TYPE_HIGH_PREC, length_greater_or_equal=True,
                               no_float32=no_float32)

    def test_array(self):
        # invalid length
        with self.assertRaises(DecoderException):
            ubjloadb(ARRAY_START + CONTAINER_COUNT + ubjdumpb(-5))
        # unencodable type within
        with self.assertRaises(EncoderException):
            ubjdumpb([type(None)])
        for sequence in list, tuple:
            self.assertEqual(ubjdumpb(sequence()), ARRAY_START + ARRAY_END)
        self.assertEqual(ubjdumpb((None,), container_count=True), (ARRAY_START + CONTAINER_COUNT + TYPE_UINT8 +
                                                                   b'\x01' + TYPE_NULL))
        obj = [123,
               1.25,
               43121609.5543,
               12345.44e40,
               Decimal('10e15'),
               'a',
               'here is a string',
               None,
               True,
               False,
               [[1, 2], 3, [4, 5, 6], 7],
               {'a dict': 456}]
        for opts in ({'container_count': False}, {'container_count': True}):
            self.check_enc_dec(obj, **opts)

    def test_bytes(self):
        # insufficient length
        with self.assertRaises(DecoderException):
            ubjloadb(ARRAY_START + CONTAINER_TYPE + TYPE_UINT8 + CONTAINER_COUNT + TYPE_UINT8 + b'\x02' + b'\x01')
        self.check_enc_dec(b'')
        self.check_enc_dec(b'\x01' * 4)
        self.assertEqual(ubjloadb(ubjdumpb(b'\x04' * 4), no_bytes=True), [4] * 4)
        self.check_enc_dec(b'largebinary' * 100)

    def test_container_fixed(self):
        raw_start = ARRAY_START + CONTAINER_TYPE + TYPE_INT8 + CONTAINER_COUNT + TYPE_UINT8
        self.assertEqual(ubjloadb(raw_start + b'\x00'), [])
        # fixed-type + count
        self.assertEqual(ubjloadb(ARRAY_START + CONTAINER_TYPE + TYPE_NULL + CONTAINER_COUNT + TYPE_UINT8 + b'\x05'),
                         [None] * 5)
        self.assertEqual(ubjloadb(raw_start + b'\x03' + (b'\x01' * 3)), [1, 1, 1])
        # invalid type
        with self.assertRaises(DecoderException):
            ubjloadb(ARRAY_START + CONTAINER_TYPE + b'\x01')
        # type without count
        with self.assertRaises(DecoderException):
            ubjloadb(ARRAY_START + CONTAINER_TYPE + TYPE_INT8 + b'\x01')

        raw_start = OBJECT_START + CONTAINER_TYPE + TYPE_INT8 + CONTAINER_COUNT + TYPE_UINT8
        self.assertEqual(ubjloadb(raw_start + b'\x00'), {})
        self.assertEqual(ubjloadb(raw_start + b'\x03' + (TYPE_UINT8 + b'\x02' + b'aa' + b'\x01' +
                                                         TYPE_UINT8 + b'\x02' + b'bb' + b'\x02' +
                                                         TYPE_UINT8 + b'\x02' + b'cc' + b'\x03')),
                         {'aa': 1, 'bb': 2, 'cc': 3})
        # fixed type + count
        self.assertEqual(ubjloadb(OBJECT_START + CONTAINER_TYPE + TYPE_NULL + CONTAINER_COUNT + TYPE_UINT8 + b'\x02' +
                                  TYPE_UINT8 + b'\x02' + b'aa' + TYPE_UINT8 + b'\x02' + b'bb'),
                         {'aa': None, 'bb': None})

        # fixed type + count (bytes)
        self.assertEqual(ubjloadb(OBJECT_START + CONTAINER_TYPE + TYPE_UINT8 + CONTAINER_COUNT + TYPE_UINT8 + b'\x02' +
                                  TYPE_UINT8 + b'\x02' + b'aa' + b'\x04' + TYPE_UINT8 + b'\x02' + b'bb' + b'\x05'),
                         {'aa': 4, 'bb': 5})

    def test_object(self):
        self.assertEqual(ubjdumpb({}), OBJECT_START + OBJECT_END)
        self.assertEqual(ubjdumpb({'a': None}, container_count=True), (OBJECT_START + CONTAINER_COUNT + TYPE_UINT8 +
                                                                       b'\x01' + TYPE_UINT8 + b'\x01' +
                                                                       'a'.encode('utf-8') + TYPE_NULL))
        self.check_enc_dec({})
        # negative length
        with self.assertRaises(DecoderException):
            ubjloadb(OBJECT_START + CONTAINER_COUNT + ubjdumpb(-1))
        with self.assertRaises(EncoderException):
            ubjdumpb({123: 'non-string key'})
        with self.assertRaises(EncoderException):
            ubjdumpb({'fish': type(list)})
        # invalid key size type
        with self.assertRaises(DecoderException):
            ubjloadb(OBJECT_START + TYPE_NULL)
        # invalid key size, key too short, key invalid utf-8, no value
        for suffix in (b'\x81', b'\x01', b'\x01' + b'\xfe', b'\x0101'):
            with self.assertRaises(DecoderException):
                ubjloadb(OBJECT_START + TYPE_INT8 + suffix)
        self.check_enc_dec({'longkey1' * 65: 1})
        self.check_enc_dec({'longkey2' * 4096: 1})

        obj = {'int': 123,
               'longint': 9223372036854775807,
               'float': 1.25,
               'hp': Decimal('10e15'),
               'char': 'a',
               'str': 'here is a string',
               'unicode': u(r'\u00a9 with extended\u2122'),
               '': 'empty key',
               u(r'\u00a9 with extended\u2122'): 'unicode-key',
               'null': None,
               'true': True,
               'false': False,
               'array': [1, 2, 3],
               'bytes_array': b'1234',
               'object': {'another one': 456, 'yet another': {'abc': True}}}
        for opts in ({'container_count': False}, {'container_count': True}):
            self.check_enc_dec(obj, **opts)

        # dictionary key sorting
        obj1 = OrderedDict.fromkeys('abcdefghijkl')
        obj2 = OrderedDict.fromkeys('abcdefghijkl'[::-1])
        self.assertNotEqual(ubjdumpb(obj1), ubjdumpb(obj2))
        self.assertEqual(ubjdumpb(obj1, sort_keys=True), ubjdumpb(obj2, sort_keys=True))

        # custom mapping class
        with self.assertRaises(TypeError):
            ubjloadb(TYPE_NULL, object_pairs_hook=list)
        self.assertEqual(ubjloadb(ubjdumpb(obj1), object_pairs_hook=OrderedDict), obj1)

    def test_circular(self):
        sequence = [1, 2, 3]
        sequence.append(sequence)
        mapping = {'a': 1, 'b': 2}
        mapping['c'] = mapping

        for container in (sequence, mapping):
            with self.assertRaises(EncoderException):
                ubjdumpb(container)

        # Refering to the same container multiple times is valid however
        sequence = [1, 2, 3]
        mapping = {'a': 1, 'b': 2}
        self.check_enc_dec([sequence, mapping, sequence, mapping])

    def test_unencodable(self):
        with self.assertRaises(EncoderException):
            ubjdumpb(type(None))

    def test_decoder_fuzz(self):
        for start, end, fmt in ((0, pow(2, 8), '>B'), (pow(2, 8), pow(2, 16), '>H')):
            for i in range(start, end):
                try:
                    ubjloadb(pack(fmt, i))
                except DecoderException:
                    pass
                except Exception as ex:  # pragma: no cover  pylint: disable=broad-except
                    self.fail('Unexpected failure: %s' % ex)

    def test_fp(self):
        obj = {"a": 123, "b": 456}
        output = BytesIO()
        ubjdump({"a": 123, "b": 456}, output)
        self.assertEqual(ubjloadb(output.getvalue()), obj)
