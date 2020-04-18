# Copyright (c) 2019 Iotic Labs Ltd. All rights reserved.
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


from sys import version_info, getrecursionlimit, setrecursionlimit
from functools import partial
from io import BytesIO, SEEK_END
from unittest import TestCase, skipUnless
from pprint import pformat
from decimal import Decimal
from struct import pack
from collections import OrderedDict

from ubjson import (dump as ubjdump, dumpb as ubjdumpb, load as ubjload, loadb as ubjloadb, EncoderException,
                    DecoderException, EXTENSION_ENABLED)
from ubjson.markers import (TYPE_NULL, TYPE_NOOP, TYPE_BOOL_TRUE, TYPE_BOOL_FALSE, TYPE_INT8, TYPE_UINT8, TYPE_INT16,
                            TYPE_INT32, TYPE_INT64, TYPE_FLOAT32, TYPE_FLOAT64, TYPE_HIGH_PREC, TYPE_CHAR, TYPE_STRING,
                            OBJECT_START, OBJECT_END, ARRAY_START, ARRAY_END, CONTAINER_TYPE, CONTAINER_COUNT)
from ubjson.compat import INTEGER_TYPES
# Pure Python versions
from ubjson.encoder import dump as ubjpuredump, dumpb as ubjpuredumpb
from ubjson.decoder import load as ubjpureload, loadb as ubjpureloadb

PY2 = version_info[0] < 3

if PY2:  # pragma: no cover
    def u(obj):
        """Casts obj to unicode string, unless already one"""
        return obj if isinstance(obj, unicode) else unicode(obj)  # noqa: F821 pylint: disable=undefined-variable
else:  # pragma: no cover
    def u(obj):
        """Casts obj to unicode string, unless already one"""
        return obj if isinstance(obj, str) else str(obj)


class TestEncodeDecodePlain(TestCase):  # pylint: disable=too-many-public-methods

    @staticmethod
    def ubjloadb(raw, *args, **kwargs):
        return ubjpureloadb(raw, *args, **kwargs)

    @staticmethod
    def ubjdumpb(obj, *args, **kwargs):
        return ubjpuredumpb(obj, *args, **kwargs)

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
                      # decoder params
                      object_hook=None,
                      object_pairs_hook=None,
                      # additional arguments to pass to encoder
                      **kwargs):
        """Black-box test to check whether the provided object is the same once encoded and subsequently decoded."""
        encoded = self.ubjdumpb(obj, **kwargs)
        if expected_type is not None:
            self.type_check(encoded[0], expected_type)
        if length is not None:
            assert_func = self.assertGreaterEqual if length_greater_or_equal else self.assertEqual
            assert_func(len(encoded), length, self.__format_in_out(obj, encoded))
        if approximate:
            self.assertTrue(self.numbers_close(self.ubjloadb(encoded, object_hook=object_hook,
                                                             object_pairs_hook=object_pairs_hook), obj),
                            msg=self.__format_in_out(obj, encoded))
        else:
            self.assertEqual(self.ubjloadb(encoded, object_hook=object_hook,
                                           object_pairs_hook=object_pairs_hook), obj,
                             self.__format_in_out(obj, encoded))

    def test_no_data(self):
        with self.assertRaises(DecoderException):
            self.ubjloadb(b'')

    def test_invalid_data(self):
        for invalid in (u('unicode'), 123):
            with self.assertRaises(TypeError):
                self.ubjloadb(invalid)

    def test_trailing_input(self):
        self.assertEqual(self.ubjloadb(TYPE_BOOL_TRUE * 10), True)

    def test_invalid_marker(self):
        with self.assertRaises(DecoderException) as ctx:
            self.ubjloadb(b'A')
        self.assertTrue(isinstance(ctx.exception.position, INTEGER_TYPES + (type(None),)))

    def test_bool(self):
        self.assertEqual(self.ubjdumpb(True), TYPE_BOOL_TRUE)
        self.assertEqual(self.ubjdumpb(False), TYPE_BOOL_FALSE)
        self.check_enc_dec(True, 1)
        self.check_enc_dec(False, 1)

    def test_null(self):
        self.assertEqual(self.ubjdumpb(None), TYPE_NULL)
        self.check_enc_dec(None, 1)

    def test_char(self):
        self.assertEqual(self.ubjdumpb(u('a')), TYPE_CHAR + 'a'.encode('utf-8'))
        # no char, char invalid utf-8
        for suffix in (b'', b'\xfe'):
            with self.assertRaises(DecoderException):
                self.ubjloadb(TYPE_CHAR + suffix)
        for char in (u('a'), u('\0'), u('~')):
            self.check_enc_dec(char, 2)

    def test_string(self):
        self.assertEqual(self.ubjdumpb(u('ab')), TYPE_STRING + TYPE_UINT8 + b'\x02' + 'ab'.encode('utf-8'))
        self.check_enc_dec(u(''), 3)
        # invalid string size, string too short, string invalid utf-8
        for suffix in (b'\x81', b'\x01', b'\x01' + b'\xfe'):
            with self.assertRaises(DecoderException):
                self.ubjloadb(TYPE_STRING + TYPE_INT8 + suffix)
        # Note: In Python 2 plain str type is encoded as byte array
        for string in ('some ascii', u(r'\u00a9 with extended\u2122'), u('long string') * 100):
            self.check_enc_dec(string, 4, length_greater_or_equal=True)

    def test_int(self):
        self.assertEqual(self.ubjdumpb(Decimal(-1.5)),
                         TYPE_HIGH_PREC + TYPE_UINT8 + b'\x04' + '-1.5'.encode('utf-8'))
        # insufficient length
        with self.assertRaises(DecoderException):
            self.ubjloadb(TYPE_INT16 + b'\x01')

        for type_, value, total_size in (
                (TYPE_UINT8, 0, 2),
                (TYPE_UINT8, 255, 2),
                (TYPE_INT8, -128, 2),
                (TYPE_INT16, -32768, 3),
                (TYPE_INT16, 456, 3),
                (TYPE_INT16, 32767, 3),
                (TYPE_INT32, -2147483648, 5),
                (TYPE_INT32, 1610612735, 5),
                (TYPE_INT32, 2147483647, 5),
                (TYPE_INT64, -9223372036854775808, 9),
                (TYPE_INT64, 6917529027641081855, 9),
                (TYPE_INT64, 9223372036854775807, 9),
                # HIGH_PREC (marker + length marker + length + value)
                (TYPE_HIGH_PREC, 9223372036854775808, 22),
                (TYPE_HIGH_PREC, -9223372036854775809, 23),
                (TYPE_HIGH_PREC, 9999999999999999999999999999999999999, 40)):
            self.check_enc_dec(value, total_size, expected_type=type_)

    def test_high_precision(self):
        self.assertEqual(self.ubjdumpb(Decimal(-1.5)),
                         TYPE_HIGH_PREC + TYPE_UINT8 + b'\x04' + '-1.5'.encode('utf-8'))
        # insufficient length, invalid utf-8, invalid decimal value
        for suffix in (b'n', b'\xfe\xfe', b'na'):
            with self.assertRaises(DecoderException):
                self.ubjloadb(TYPE_HIGH_PREC + TYPE_UINT8 + b'\x02' + suffix)

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
            self.assertEqual(self.ubjloadb(self.ubjdumpb(Decimal(value))), None)

    def test_float(self):
        # insufficient length
        for float_type in (TYPE_FLOAT32, TYPE_FLOAT64):
            with self.assertRaises(DecoderException):
                self.ubjloadb(float_type + b'\x01')

        self.check_enc_dec(0.0, 5, expected_type=TYPE_FLOAT32)

        for type_, value, total_size in (
                (TYPE_FLOAT32, 1.18e-37, 5),
                (TYPE_FLOAT32, 3.4e37, 5),
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
                self.assertEqual(self.ubjloadb(self.ubjdumpb(float(value), no_float32=no_float32)), None)
        # value which results in high_prec usage
        for no_float32 in (True, False):
            self.check_enc_dec(2.22e-308, 4, expected_type=TYPE_HIGH_PREC, length_greater_or_equal=True,
                               no_float32=no_float32)

    def test_array(self):
        # invalid length
        with self.assertRaises(DecoderException):
            self.ubjloadb(ARRAY_START + CONTAINER_COUNT + self.ubjdumpb(-5))
        # unencodable type within
        with self.assertRaises(EncoderException):
            self.ubjdumpb([type(None)])
        for sequence in list, tuple:
            self.assertEqual(self.ubjdumpb(sequence()), ARRAY_START + ARRAY_END)
        self.assertEqual(self.ubjdumpb((None,), container_count=True), (ARRAY_START + CONTAINER_COUNT + TYPE_UINT8 +
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
            self.ubjloadb(ARRAY_START + CONTAINER_TYPE + TYPE_UINT8 + CONTAINER_COUNT + TYPE_UINT8 + b'\x02' + b'\x01')
        for cast in (bytes, bytearray):
            self.check_enc_dec(cast(b''))
            self.check_enc_dec(cast(b'\x01' * 4))
            self.assertEqual(self.ubjloadb(self.ubjdumpb(cast(b'\x04' * 4)), no_bytes=True), [4] * 4)
            self.check_enc_dec(cast(b'largebinary' * 100))

    def test_array_fixed(self):
        raw_start = ARRAY_START + CONTAINER_TYPE + TYPE_INT8 + CONTAINER_COUNT + TYPE_UINT8
        self.assertEqual(self.ubjloadb(raw_start + b'\x00'), [])

        # fixed types + count
        for ubj_type, py_obj in ((TYPE_NULL, None), (TYPE_BOOL_TRUE, True), (TYPE_BOOL_FALSE, False)):
            self.assertEqual(
                self.ubjloadb(ARRAY_START + CONTAINER_TYPE + ubj_type + CONTAINER_COUNT + TYPE_UINT8 + b'\x05'),
                [py_obj] * 5
            )
        self.assertEqual(self.ubjloadb(raw_start + b'\x03' + (b'\x01' * 3)), [1, 1, 1])

        # invalid type
        with self.assertRaises(DecoderException):
            self.ubjloadb(ARRAY_START + CONTAINER_TYPE + b'\x01')

        # type without count
        with self.assertRaises(DecoderException):
            self.ubjloadb(ARRAY_START + CONTAINER_TYPE + TYPE_INT8 + b'\x01')

        # count without type
        self.assertEqual(self.ubjloadb(ARRAY_START + CONTAINER_COUNT + TYPE_UINT8 + b'\x02' + TYPE_BOOL_FALSE +
                                       TYPE_BOOL_TRUE),
                         [False, True])

        # nested
        self.assertEqual(self.ubjloadb(ARRAY_START + CONTAINER_TYPE + ARRAY_START + CONTAINER_COUNT + TYPE_UINT8 +
                                       b'\x03' + ARRAY_END + CONTAINER_COUNT + TYPE_UINT8 + b'\x01' + TYPE_BOOL_TRUE +
                                       TYPE_BOOL_FALSE + TYPE_BOOL_TRUE + ARRAY_END),
                         [[], [True], [False, True]])

    def test_array_noop(self):
        # only supported without type
        self.assertEqual(self.ubjloadb(ARRAY_START +
                                       TYPE_NOOP +
                                       TYPE_UINT8 + b'\x01' +
                                       TYPE_NOOP +
                                       TYPE_UINT8 + b'\x02' +
                                       TYPE_NOOP +
                                       ARRAY_END), [1, 2])
        self.assertEqual(self.ubjloadb(ARRAY_START + CONTAINER_COUNT + TYPE_UINT8 + b'\x01' +
                                       TYPE_NOOP +
                                       TYPE_UINT8 + b'\x01'), [1])

    def test_object_invalid(self):
        # negative length
        with self.assertRaises(DecoderException):
            self.ubjloadb(OBJECT_START + CONTAINER_COUNT + self.ubjdumpb(-1))

        with self.assertRaises(EncoderException):
            self.ubjdumpb({123: 'non-string key'})

        with self.assertRaises(EncoderException):
            self.ubjdumpb({'fish': type(list)})

        # invalid key size type
        with self.assertRaises(DecoderException):
            self.ubjloadb(OBJECT_START + TYPE_NULL)

        # invalid key size, key too short, key invalid utf-8, no value
        for suffix in (b'\x81', b'\x01', b'\x01' + b'\xfe', b'\x0101'):
            with self.assertRaises(DecoderException):
                self.ubjloadb(OBJECT_START + TYPE_INT8 + suffix)

        # invalid items() method
        class BadDict(dict):
            def items(self):
                return super(BadDict, self).keys()

        with self.assertRaises(ValueError):
            self.ubjdumpb(BadDict({'a': 1, 'b': 2}))

    def test_object(self):
        # custom hook
        with self.assertRaises(TypeError):
            self.ubjloadb(self.ubjdumpb({}), object_pairs_hook=int)
        # same as not specifying a custom class
        self.ubjloadb(self.ubjdumpb({}), object_pairs_hook=None)

        for hook in (None, OrderedDict):
            check_enc_dec = partial(self.check_enc_dec, object_pairs_hook=hook)

            self.assertEqual(self.ubjdumpb({}), OBJECT_START + OBJECT_END)
            self.assertEqual(self.ubjdumpb({'a': None}, container_count=True),
                             (OBJECT_START + CONTAINER_COUNT + TYPE_UINT8 + b'\x01' + TYPE_UINT8 + b'\x01' +
                              'a'.encode('utf-8') + TYPE_NULL))
            check_enc_dec({})
            check_enc_dec({'longkey1' * 65: 1})
            check_enc_dec({'longkey2' * 4096: 1})

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
                check_enc_dec(obj, **opts)

        # dictionary key sorting
        obj1 = OrderedDict.fromkeys('abcdefghijkl')
        obj2 = OrderedDict.fromkeys('abcdefghijkl'[::-1])
        self.assertNotEqual(self.ubjdumpb(obj1), self.ubjdumpb(obj2))
        self.assertEqual(self.ubjdumpb(obj1, sort_keys=True), self.ubjdumpb(obj2, sort_keys=True))

        self.assertEqual(self.ubjloadb(self.ubjdumpb(obj1), object_pairs_hook=OrderedDict), obj1)

    def test_object_fixed(self):
        raw_start = OBJECT_START + CONTAINER_TYPE + TYPE_INT8 + CONTAINER_COUNT + TYPE_UINT8

        for hook in (None, OrderedDict):
            loadb = partial(self.ubjloadb, object_pairs_hook=hook)

            self.assertEqual(loadb(raw_start + b'\x00'), {})
            self.assertEqual(loadb(raw_start + b'\x03' + (TYPE_UINT8 + b'\x02' + b'aa' + b'\x01' +
                                                          TYPE_UINT8 + b'\x02' + b'bb' + b'\x02' +
                                                          TYPE_UINT8 + b'\x02' + b'cc' + b'\x03')),
                             {'aa': 1, 'bb': 2, 'cc': 3})

            # count only
            self.assertEqual(loadb(OBJECT_START + CONTAINER_COUNT + TYPE_UINT8 + b'\x02' +
                                   TYPE_UINT8 + b'\x02' + b'aa' + TYPE_NULL + TYPE_UINT8 + b'\x02' + b'bb' + TYPE_NULL),
                             {'aa': None, 'bb': None})

            # fixed type + count
            self.assertEqual(loadb(OBJECT_START + CONTAINER_TYPE + TYPE_NULL + CONTAINER_COUNT + TYPE_UINT8 + b'\x02' +
                                   TYPE_UINT8 + b'\x02' + b'aa' + TYPE_UINT8 + b'\x02' + b'bb'),
                             {'aa': None, 'bb': None})

            # fixed type + count (bytes)
            self.assertEqual(loadb(OBJECT_START + CONTAINER_TYPE + TYPE_UINT8 + CONTAINER_COUNT + TYPE_UINT8 + b'\x02' +
                                   TYPE_UINT8 + b'\x02' + b'aa' + b'\x04' + TYPE_UINT8 + b'\x02' + b'bb' + b'\x05'),
                             {'aa': 4, 'bb': 5})

    def test_object_noop(self):
        # only supported without type
        for hook in (None, OrderedDict):
            loadb = partial(self.ubjloadb, object_pairs_hook=hook)
            self.assertEqual(loadb(OBJECT_START +
                                   TYPE_NOOP +
                                   TYPE_UINT8 + b'\x01' + 'a'.encode('utf-8') + TYPE_NULL +
                                   TYPE_NOOP +
                                   TYPE_UINT8 + b'\x01' + 'b'.encode('utf-8') + TYPE_BOOL_TRUE +
                                   OBJECT_END), {'a': None, 'b': True})
            self.assertEqual(loadb(OBJECT_START + CONTAINER_COUNT + TYPE_UINT8 + b'\x01' +
                                   TYPE_NOOP +
                                   TYPE_UINT8 + b'\x01' + 'a'.encode('utf-8') + TYPE_NULL), {'a': None})

    def test_intern_object_keys(self):
        encoded = self.ubjdumpb({'asdasd': 1, 'qwdwqd': 2})
        mapping2 = self.ubjloadb(encoded, intern_object_keys=True)
        mapping3 = self.ubjloadb(encoded, intern_object_keys=True)
        for key1, key2 in zip(sorted(mapping2.keys()), sorted(mapping3.keys())):
            if PY2:  # pragma: no cover
                # interning of unicode not supported
                self.assertEqual(key1, key2)
            else:  # pragma: no cover
                self.assertIs(key1, key2)

    def test_circular(self):
        sequence = [1, 2, 3]
        sequence.append(sequence)
        mapping = {'a': 1, 'b': 2}
        mapping['c'] = mapping

        for container in (sequence, mapping):
            with self.assertRaises(ValueError):
                self.ubjdumpb(container)

        # Refering to the same container multiple times is valid however
        sequence = [1, 2, 3]
        mapping = {'a': 1, 'b': 2}
        self.check_enc_dec([sequence, mapping, sequence, mapping])

    def test_unencodable(self):
        with self.assertRaises(EncoderException):
            self.ubjdumpb(type(None))

    def test_decoder_fuzz(self):
        for start, end, fmt in ((0, pow(2, 8), '>B'), (pow(2, 8), pow(2, 16), '>H'), (pow(2, 16), pow(2, 18), '>I')):
            for i in range(start, end):
                try:
                    self.ubjloadb(pack(fmt, i))
                except DecoderException:
                    pass
                except Exception as ex:  # pragma: no cover  pylint: disable=broad-except
                    self.fail('Unexpected failure: %s' % ex)

    def assert_raises_regex(self, *args, **kwargs):
        # pylint: disable=deprecated-method,no-member
        return (self.assertRaisesRegexp if PY2 else self.assertRaisesRegex)(*args, **kwargs)

    def test_recursion(self):
        old_limit = getrecursionlimit()
        setrecursionlimit(200)
        try:
            obj = current = []
            for _ in range(getrecursionlimit() * 2):
                new_list = []
                current.append(new_list)
                current = new_list

            with self.assert_raises_regex(RuntimeError, 'recursion'):
                self.ubjdumpb(obj)

            raw = ARRAY_START * (getrecursionlimit() * 2)
            with self.assert_raises_regex(RuntimeError, 'recursion'):
                self.ubjloadb(raw)
        finally:
            setrecursionlimit(old_limit)

    def test_encode_default(self):
        def default(obj):
            if isinstance(obj, set):
                return sorted(obj)
            raise EncoderException('__test__marker__')

        dumpb_default = partial(self.ubjdumpb, default=default)
        # Top-level custom type
        obj1 = {1, 2, 3}
        obj2 = default(obj1)
        # Custom type within sequence or mapping
        obj3 = OrderedDict(sorted({'a': 1, 'b': obj1, 'c': [2, obj1]}.items()))
        obj4 = OrderedDict(sorted({'a': 1, 'b': obj2, 'c': [2, obj2]}.items()))

        with self.assert_raises_regex(EncoderException, 'Cannot encode item'):
            self.ubjdumpb(obj1)
        # explicit None should behave the same as no default
        with self.assert_raises_regex(EncoderException, 'Cannot encode item'):
            self.ubjdumpb(obj1, default=None)

        with self.assert_raises_regex(EncoderException, '__test__marker__'):
            dumpb_default(self)

        self.assertEqual(dumpb_default(obj1), self.ubjdumpb(obj2))
        self.assertEqual(dumpb_default(obj3), self.ubjdumpb(obj4))

    def test_decode_object_hook(self):
        with self.assertRaises(TypeError):
            self.check_enc_dec({'a': 1, 'b': 2}, object_hook=int)

        def default(obj):
            if isinstance(obj, set):
                return {'__set__': list(obj)}
            raise EncoderException('__test__marker__')

        def object_hook(obj):
            if '__set__' in obj:
                return set(obj['__set__'])
            return obj

        self.check_enc_dec({'a': 1, 'b': {2, 3, 4}}, object_hook=object_hook, default=default)

        class UnHandled(object):
            pass

        with self.assertRaises(EncoderException):
            self.check_enc_dec({'a': 1, 'b': UnHandled()}, object_hook=object_hook, default=default)


@skipUnless(EXTENSION_ENABLED, 'Extension not enabled')
class TestEncodeDecodePlainExt(TestEncodeDecodePlain):

    @staticmethod
    def ubjloadb(raw, *args, **kwargs):
        return ubjloadb(raw, *args, **kwargs)

    @staticmethod
    def ubjdumpb(obj, *args, **kwargs):
        return ubjdumpb(obj, *args, **kwargs)


class TestEncodeDecodeFp(TestEncodeDecodePlain):
    """Performs tests via file-like objects (BytesIO) instead of bytes instances"""

    @staticmethod
    def ubjloadb(raw, *args, **kwargs):
        return ubjpureload(BytesIO(raw), *args, **kwargs)

    @staticmethod
    def ubjdumpb(obj, *args, **kwargs):
        out = BytesIO()
        ubjpuredump(obj, out, *args, **kwargs)
        return out.getvalue()

    @staticmethod
    def ubjload(fp, *args, **kwargs):
        return ubjpureload(fp, *args, **kwargs)

    @staticmethod
    def ubjdump(obj, fp, *args, **kwargs):
        return ubjpuredump(obj, fp, *args, **kwargs)

    def test_decode_exception_position(self):
        with self.assertRaises(DecoderException) as ctx:
            self.ubjloadb(TYPE_STRING + TYPE_INT8 + b'\x01' + b'\xfe' + b'c0fefe' * 4)
        self.assertEqual(ctx.exception.position, 4)

    def test_invalid_fp_dump(self):
        with self.assertRaises(AttributeError):
            self.ubjdump(None, 1)

        class Dummy(object):
            write = 1

        class Dummy2(object):
            @staticmethod
            def write(raw):
                raise ValueError('invalid - %s' % repr(raw))

        with self.assertRaises(TypeError):
            self.ubjdump(b'', Dummy)

        with self.assertRaises(ValueError):
            self.ubjdump(b'', Dummy2)

    def test_invalid_fp_load(self):
        with self.assertRaises(AttributeError):
            self.ubjload(1)

        class Dummy(object):
            read = 1

        class Dummy2(object):

            @staticmethod
            def read(length):
                raise ValueError('invalid - %d' % length)

        with self.assertRaises(TypeError):
            self.ubjload(Dummy)

        with self.assertRaises(ValueError):
            self.ubjload(Dummy2)

    def test_fp(self):
        obj = {'a': 123, 'b': 456}
        output = BytesIO()
        self.ubjdump(obj, output)
        output.seek(0)
        self.assertEqual(self.ubjload(output), obj)


@skipUnless(EXTENSION_ENABLED, 'Extension not enabled')
class TestEncodeDecodeFpExt(TestEncodeDecodeFp):

    @staticmethod
    def ubjloadb(raw, *args, **kwargs):
        return ubjload(BytesIO(raw), *args, **kwargs)

    @staticmethod
    def ubjdumpb(obj, *args, **kwargs):
        out = BytesIO()
        ubjdump(obj, out, *args, **kwargs)
        return out.getvalue()

    @staticmethod
    def ubjload(fp, *args, **kwargs):
        return ubjload(fp, *args, **kwargs)

    @staticmethod
    def ubjdump(obj, fp, *args, **kwargs):
        return ubjdump(obj, fp, *args, **kwargs)

    # Seekable file-like object buffering
    def test_fp_buffer(self):
        output = BytesIO()

        # items which fit into extension decoder-internal read buffer (BUFFER_FP_SIZE in decoder.c, extension only)
        obj2 = ['fishy' * 64] * 10
        output.seek(0)
        self.ubjdump(obj2, output)
        output.seek(0)
        self.assertEqual(self.ubjload(output), obj2)

        # larger than extension read buffer (extension only)
        obj3 = ['fishy' * 512] * 10
        output.seek(0)
        self.ubjdump(obj3, output)
        output.seek(0)
        self.assertEqual(self.ubjload(output), obj3)

    # Multiple documents in same stream (issue #9)
    def test_fp_multi(self):
        obj = {'a': 123, 'b': b'some raw content'}
        output = BytesIO()
        count = 10

        # Seekable an non-seekable runs
        for _ in range(2):
            output.seek(0)

            for i in range(count):
                obj['c'] = i
                self.ubjdump(obj, output)

            output.seek(0)
            for i in range(count):
                obj['c'] = i
                self.assertEqual(self.ubjload(output), obj)

            output.seekable = lambda: False

    # Whole "token" in decoder input unavailable (in non-seekable file-like object)
    def test_fp_callable_incomplete(self):
        obj = [123, b'something']
        # remove whole of last token (binary data 'something', without its length)
        output = BytesIO(self.ubjdumpb(obj)[:-(len(obj[1]) + 1)])
        output.seekable = lambda: False

        with self.assert_raises_regex(DecoderException, 'Insufficient input'):
            self.ubjload(output)

    def test_fp_seek_invalid(self):
        output = BytesIO()
        self.ubjdump({'a': 333, 'b': 444}, output)
        # pad with data (non-ubjson) to ensure buffering too much data
        output.write(b' ' * 16)
        output.seek(0)

        output.seek_org = output.seek

        # seek fails
        def bad_seek(*_):
            raise OSError('bad seek')

        output.seek = bad_seek
        with self.assert_raises_regex(OSError, 'bad seek'):
            self.ubjload(output)

        # decoding (lack of input) and seek fail - should get decoding failure
        output.seek_org(0, SEEK_END)
        with self.assert_raises_regex(DecoderException, 'Insufficient input'):
            self.ubjload(output)

        # seek is not callable
        output.seek_org(0)
        output.seek = True
        with self.assert_raises_regex(TypeError, 'not callable'):
            self.ubjload(output)

        # decoding (lack of input) and seek not callable - should get decoding failure
        output.seek_org(0, SEEK_END)
        with self.assert_raises_regex(DecoderException, 'Insufficient input'):
            self.ubjload(output)


# def pympler_run(iterations=20):
#     from unittest import main
#     from pympler import tracker
#     from gc import collect

#     tracker = tracker.SummaryTracker()
#     for i in range(iterations):
#         try:
#             main()
#         except SystemExit:
#             pass
#         if i % 2:
#             collect()
#             tracker.print_diff()


# if __name__ == '__main__':
#     pympler_run()
