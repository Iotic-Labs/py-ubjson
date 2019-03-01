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

from __future__ import print_function, unicode_literals

from abc import ABCMeta, abstractmethod
from sys import argv
from traceback import print_exc
from types import GeneratorType
from contextlib import contextmanager
from time import time
import gc
import cProfile

from json import __version__ as j_version, dumps as j_enc, loads as j_dec, load as j_load

# ------------------------------------------------------------------------------


class LibWrapper(object):

    __metaclass__ = ABCMeta

    @staticmethod
    @abstractmethod
    def name():
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def encode(obj):
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def decode(obj):
        raise NotImplementedError


# Python's built-in JSON module

class Json(LibWrapper):

    @staticmethod
    def name():
        return 'json %s' % j_version

    @staticmethod
    def encode(obj):
        return j_enc(obj)

    @staticmethod
    def decode(obj):
        return j_dec(obj)


TEST_LIBS = [Json]

# py-ubjson

try:
    from ubjson import __version__ as ubj_version, dumpb as ubj_enc, loadb as ubj_dec
except ImportError:
    print('Failed to import ubjson, ignoring')
else:
    class PyUbjson(LibWrapper):

        @staticmethod
        def name():
            return 'py-ubjson %s' % ubj_version

        @staticmethod
        def encode(obj):
            return ubj_enc(obj)

        @staticmethod
        def decode(obj):
            return ubj_dec(obj)
    TEST_LIBS.append(PyUbjson)

# simpleubjson

try:
    from simpleubjson import __version__ as subj_version, encode as subj_enc, decode as subj_dec
except ImportError:
    print('Failed to import simpleubjson, ignoring')
else:
    class SimpleUbjson(LibWrapper):

        @staticmethod
        def name():
            return 'simpleubjson %s' % subj_version

        @staticmethod
        def encode(obj):
            return subj_enc(obj)

        @staticmethod
        def decode(obj):
            val = subj_dec(obj)
            # ugly: decoder only returns iterator if object or array (and only know by name of generator which it is)
            if isinstance(val, GeneratorType):
                if val.__name__ == 'array_stream':
                    return list(val)
                else:
                    return dict(val)
            else:
                return val
    TEST_LIBS.append(SimpleUbjson)

# ------------------------------------------------------------------------------


@contextmanager
def profiled(name=None, no_profile=False):
    if no_profile:
        yield
    else:
        profile = cProfile.Profile()
        profile.enable()
        try:
            yield
        finally:
            profile.disable()
        if name:
            print('stats for %s' % name)
        profile.print_stats('tottime')


def test_all_with(name, repeats=1000):
    no_profile = True

    with open(name, 'r') as in_file:
        obj = j_load(in_file)
        print('%s (%d)' % (name, in_file.tell()))

    gc.disable()
    for lib in TEST_LIBS:
        start = time()
        with profiled(lib.name(), no_profile=no_profile):
            for _ in range(repeats):
                lib.encode(obj)
        enc_time = time() - start
        gc.collect()

        encoded = lib.encode(obj)
        start = time()
        with profiled(lib.name(), no_profile=no_profile):
            for _ in range(repeats):
                lib.decode(encoded)
        dec_time = time() - start
        gc.collect()

        print('%20s (enc/dec): %.3f / %.3f' % (lib.name(), enc_time, dec_time))
    gc.enable()


def main():
    try:
        if len(argv) < 3:
            raise ValueError
        repeats = int(argv[1])
        if repeats < 1:
            raise ValueError
    except ValueError:
        print('USAGE: perf.py REPEATS INPUT1 [INPUT2] ..')
        return 1

    print('Testing with %d repeats' % repeats)
    for name in argv[2:]:
        try:
            test_all_with(name, repeats=repeats)
        except:  # pylint: disable=bare-except
            print('Failed to test with %s' % name)
            print_exc()
            return 2

    return 0


if __name__ == "__main__":
    exit(main())
