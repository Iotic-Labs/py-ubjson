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

# pylint: disable=import-error,wrong-import-order

import sys
import os
import warnings
from glob import iglob

# Allow for environments without setuptools
try:
    from setuptools import setup
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

from distutils.core import Extension
from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError
from distutils.errors import DistutilsPlatformError, DistutilsExecError

from ubjson import __version__ as version


# For converting markdown README.md
try:
    from pypandoc import convert
except ImportError:
    READ_MD = lambda f: open(f, 'r').read()
    print('Warning: pypandoc module not found, will not convert Markdown to RST')
else:
    READ_MD = lambda f: convert(f, 'rst')


# Loosely based on https://github.com/mongodb/mongo-python-driver/blob/master/setup.py
class BuildExtWarnOnFail(build_ext):
    """Allow for extension building to fail."""

    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            ex = sys.exc_info()[1]
            sys.stdout.write('%s\n' % str(ex))
            warnings.warn("Extension modules: There was an issue with your platform configuration - see above.")

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except (CCompilerError, DistutilsExecError, DistutilsPlatformError, IOError):
            ex = sys.exc_info()[1]
            sys.stdout.write('%s\n' % str(ex))
            warnings.warn("Extension module %s: The output above this warning shows how the compilation failed."
                          % ext.name)


EXTENSION = '.py3.c' if sys.version_info[0] >= 3 else '.py2.c'
BUILD_EXTENSIONS = 'PYUBJSON_NO_EXTENSION' not in os.environ

setup(
    name='py-ubjson',
    version=version,
    description='Universal Binary JSON encoder/decoder',
    long_description=READ_MD('README.md'),
    author='Iotic Labs Ltd',
    author_email='info@iotic-labs.com',
    maintainer='Iotic Labs Ltd',
    maintainer_email='vilnis.termanis@iotic-labs.com',
    url='https://github.com/Iotic-Labs/py-ubjson',
    license='Apache License 2.0',
    packages=['ubjson'],
    zip_safe=False,
    ext_modules=([Extension(name[:-len(EXTENSION)], [name]) for name in iglob('ubjson/*' + EXTENSION)]
                 if BUILD_EXTENSIONS else []),
    cmdclass={"build_ext": BuildExtWarnOnFail},
    keywords=['ubjson', 'ubj'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: Apache Software License',
        'Intended Audience :: Developers',
        'Programming Language :: C',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules'
        ]
    )
