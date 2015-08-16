"""Python v2.7 (NOT 2.6) compatibility"""

# Original six.py copyright notice, on which snippets herein are based:
#
# Copyright (c) 2010-2015 Benjamin Peterson
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from sys import version_info

PY2 = version_info[0] == 2

if PY2:
    # pylint:disable=undefined-variable
    integer_types = (int, long)  # noqa
    # pylint: disable=unused-import
    from collections import Mapping, Sequence  # noqa
else:

    integer_types = int
    # pylint: disable=unused-import
    from collections.abc import Mapping, Sequence  # noqa


if version_info[:2] == (3, 2):
    # pylint: disable=exec-used
    exec("""def raise_from(value, from_value):
    if from_value is None:
        raise value
    raise value from from_value
""")
elif version_info[:2] > (3, 2):
    # pylint: disable=exec-used
    exec("""def raise_from(value, from_value):
    raise value from from_value
""")
else:
    def raise_from(value, _):
        raise value
