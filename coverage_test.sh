#!/usr/bin/env bash
set -eu

# Requirements
# ------------
# Python: coverage
# C: Gcov (GCC), lcov

git clean -fdX build/ _ubjson*.so
rm -rf coverage/{c,python}

# Coverage should be measured with extension compiled for both Python 2 & 3 (e.g. via separate venv)
export CFLAGS="-coverage"
python setup.py build_ext -i
python -mcoverage run --branch --omit=ubjson/compat.py -m unittest discover test/ -vf
python -mcoverage html -d coverage/python
lcov --capture --directory . --output-file /tmp/ubjson-coverage.info.pre
# Only consider own source files. (Unfortunately extract/remove commands seem incapable of reading from stdin)
lcov --extract /tmp/ubjson-coverage.info.pre "$(pwd)/src/*" --output-file /tmp/ubjson-coverage.info.pre2
# Exclude CPython floating point logic in coverage
lcov --remove /tmp/ubjson-coverage.info.pre2 '*/src/python_funcs.*' --output-file /tmp/ubjson-coverage.info
genhtml /tmp/ubjson-coverage.info --output-directory coverage/c --legend
echo -e "\nFor coverage results see index.html in coverage sub-directories.\n"
