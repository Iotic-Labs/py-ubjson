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


"""UBJSON (draft 12) implementation without No-Op support

Example usage:

# To encode
encoded = ubjson.dumpb({'a': 1})

# To decode
decoded = ubjson.loadb(encoded)

To use a file-like object as input/output, use dump() & load() methods instead.
"""

from .encoder import dump, dumpb, EncoderException  # noqa
from .decoder import load, loadb, DecoderException  # noqa

__version__ = '0.8.0'

__all__ = ('EXTENSION_ENABLED', 'dump', 'dumpb', 'EncoderException', 'load', 'loadb', 'DecoderException')

# Whether cython extension is in use
try:
    __compiled()  # pylint: disable=undefined-variable
except NameError:
    EXTENSION_ENABLED = False
else:
    EXTENSION_ENABLED = True  # pragma: no cover
