# Copyright (c) 2015, Iotic Labs Ltd.
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

__version__ = '0.5'

__all__ = ('extension_enabled', 'dump', 'dumpb', 'EncoderException', 'load', 'loadb', 'DecoderException')

# Whether cython extension is in use
try:
    __compiled()  # pylint: disable=undefined-variable
except NameError:
    extension_enabled = False
else:
    extension_enabled = True


# pylint: disable=unused-import
from .encoder import dump, dumpb, EncoderException  # noqa
# pylint: disable=unused-import
from .decoder import load, loadb, DecoderException  # noqa
