#!/usr/bin/env bash

# Requirements
# ------------
# Python: coverage
# C: Gcov (GCC), lcov

git clean -fdX build/ _ubjson*.so

# Coverage should be measured with extension compiled for both Python 2 & 3 (e.g. via venv)
export CFLAGS="-coverage"
python setup.py build_ext -i
python -mcoverage run --branch --omit=ubjson/compat.py -m unittest discover test/ -v
python -mcoverage html -d coverage/python
lcov --capture --directory . --output-file /tmp/ubjson-coverage.info
genhtml /tmp/ubjson-coverage.info --output-directory coverage/c
echo -e "\nFor coverage results see index.html in coverage sub-directories.\n"
