# Copyright (c) 2015, V. Termanis, Iotic Labs Ltd.
# All rights reserved.
# Licensed under 2-clause BSD license - see LICENSE file for details.

"""Converts between json & ubjson"""

from __future__ import print_function
from sys import argv, stderr, stdout, stdin
from json import load as jload, dump as jdump

from .compat import stdin_raw, stdout_raw
from . import dump as ubjdump, load as ubjload, EncoderException, DecoderException


def __error(*args, **kwargs):
    print(*args, file=stderr, **kwargs)


def from_json(inStream, outStream):
    try:
        obj = jload(inStream)
    except ValueError as e:
        __error('Failed to decode json: %s' % e)
        return 8
    try:
        ubjdump(obj, outStream, sort_keys=True)
    except EncoderException as e:
        __error('Failed to encode to ubsjon: %s' % e)
        return 16
    return 0


def to_json(inStream, outStream):
    try:
        obj = ubjload(inStream)
    except DecoderException as e:
        __error('Failed to decode ubjson: %s' % e)
        return 8
    try:
        jdump(obj, outStream, sort_keys=True)
    except TypeError as e:
        __error('Failed to encode to sjon: %s' % e)
        return 16
    return 0


__action = frozenset(('fromjson', 'tojson'))


def main():  # noqa (complexity)
    if not (3 <= len(argv) <= 4 and argv[1] in __action):
        print("""USAGE: ubjson (fromjson|tojson) (INFILE|-) [OUTFILE]

Converts an objects between json and ubjson formats. Input is read from INFILE
unless set to '-', in which case stdin is used. If OUTFILE is not
specified, output goes to stdout.""", file=stderr)
        return 1

    fromJson = (argv[1] == 'fromjson')
    inFile = outFile = None
    try:
        # input
        if argv[2] == '-':
            inStream = stdin if fromJson else stdin_raw
        else:
            try:
                inStream = inFile = open(argv[2], 'r' if fromJson else 'rb')
            except IOError as e:
                __error('Failed to open input file for reading: %s' % e)
                return 2
        # output
        if len(argv) == 3:
            outStream = stdout_raw if fromJson else stdout
        else:
            try:
                outStream = outFile = open(argv[2], 'ab' if fromJson else 'a')
            except IOError as e:
                __error('Failed to open output file for writing: %s' % e)
                return 4

        return (from_json if fromJson else to_json)(inStream, outStream)
    except IOError as e:
        __error('I/O failure: %s' % e)
    finally:
        if inFile:
            inFile.close()
        if outFile:
            outFile.close()


if __name__ == "__main__":
    exit(main())
