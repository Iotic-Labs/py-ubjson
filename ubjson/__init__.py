# Copyright (c) 2015 Iotic Labs Ltd. All rights reserved.

"""UBJSON (draft 12) implementation without No-Op support

Example usage:

# To encode
encoded = ubjson.dumpb({'a': 1})

# To decode
decoded = ubjson.loadb(encoded)

To use a file-like object as input/output, use dump() & load() methods instead.
"""

__version__ = '0.5'

__all__ = ('EXTENSION_ENABLED', 'dump', 'dumpb', 'EncoderException', 'load', 'loadb', 'DecoderException')

# Whether cython extension is in use
try:
    __compiled()  # pylint: disable=undefined-variable
except NameError:
    EXTENSION_ENABLED = False
else:
    EXTENSION_ENABLED = True


# pylint: disable=unused-import
from .encoder import dump, dumpb, EncoderException  # noqa
# pylint: disable=unused-import
from .decoder import load, loadb, DecoderException  # noqa
