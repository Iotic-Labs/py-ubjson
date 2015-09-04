# Copyright (c) 2015, Iotic Labs Ltd.
# All rights reserved.
# Licensed under 2-clause BSD license - see LICENSE file for details.

import sys
import warnings
from glob import iglob
from distutils.core import setup, Extension
from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError
from distutils.errors import DistutilsPlatformError, DistutilsExecError

from ubjson import __version__ as version


# Loosely based on https://github.com/mongodb/mongo-python-driver/blob/master/setup.py
class build_ext_warn_on_fail(build_ext):
    """Allow for extension building to fail."""

    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            e = sys.exc_info()[1]
            sys.stdout.write('%s\n' % str(e))
            warnings.warn("Extension modules: There was an issue with your "
                          "platform configuration - see above.")

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except (CCompilerError, DistutilsExecError, DistutilsPlatformError, IOError):
            e = sys.exc_info()[1]
            sys.stdout.write('%s\n' % str(e))
            warnings.warn("Extension module %s: The output above this warning "
                          " shows how the compilation failed." % ext.name)


extension = '.py3.c' if sys.version_info[0] >= 3 else '.py2.c'

setup(
    name='ubjson',
    version=version,
    description='Universal Binary JSON encoder/decoder',
    author='Iotic Labs Ltd.',
    author_email='info@iotic-labs.com',
    maintainer='Vilnis Termanis',
    maintainer_email='vilnis.termanis@iotic-labs.com',
    url='https://github.com/Iotic-Labs/py-ubjson',
    license='BSD 2-clause',
    packages=['ubjson'],
    ext_modules=[Extension(name[:-len(extension)], [name]) for name in iglob('ubjson/*' + extension)],
    cmdclass={"build_ext": build_ext_warn_on_fail},
    classifiers=(
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: C',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules'
        )
    )
