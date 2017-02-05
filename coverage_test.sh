#!/usr/bin/env bash

# coverage currently only measured without extension, so clean out first
git clean -fXd ubjson
python3 -mcoverage run --omit=ubjson/compat.py -m unittest discover test/ -v
python3 -mcoverage html
echo -e "\nFor coverage results see htmlcov/index.html\n"
