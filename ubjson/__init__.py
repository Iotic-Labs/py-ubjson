# Copyright (c) 2015, V. Termanis, Iotic Labs Ltd.
# All rights reserved.
# Licensed under 2-clause BSD license - see LICENSE file for details.

"""UBJSON (draft 12) implementation without No-Op support

Example usage:

# To encode
encoded = ubjson.dumpb({'a': 1})

# To decode
decoded = ubjson.loadb(encoded)

To use a file-like object as input/output, use dump() & load() methods instead.
"""

__version__ = '0.4'

__all__ = ('dump', 'dumpb', 'EncoderException', 'load', 'loadb', 'DecoderException')

# pylint: disable=unused-import
from .encoder import dump, dumpb, EncoderException  # noqa
# pylint: disable=unused-import
from .decoder import load, loadb, DecoderException  # noqa
