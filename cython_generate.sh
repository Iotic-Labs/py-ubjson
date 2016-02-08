#!/usr/bin/env bash

# Re-generate extension modules - this has to be called if any change is made to
# any .py or .pxd

# code generation can fail if out-of-date compiled extensions exist in-place
git clean -fXd ubjson
for ext in ubjson/*.py; do
    # ext="ubjson/${ext}.py"
    # exclude module main so still works when using compiled extensions
    if [ "$ext" != "ubjson/__main__.py" ] && [ "$ext" != "ubjson/__init__.py" ]; then
        echo "Generating code for ${ext}"
        python3 -mcython -a -3 -f --fast-fail -Werror -Wextra -o ${ext}3.c ${ext} &&
        python3 -mcython -a -2 -f --fast-fail -Werror -Wextra -o ${ext}2.c ${ext}
        if [ $? -ne 0 ]; then
          exit 1
        fi
    fi
done
