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
from .compat import EXTENSION_ENABLED

__version__ = '0.8.5'

__all__ = ('EXTENSION_ENABLED', 'dump', 'dumpb', 'EncoderException', 'load', 'loadb', 'DecoderException')
