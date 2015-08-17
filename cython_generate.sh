#!/usr/bin/env bash

# Re-generate extension modules - this has to be called if any change is made to
# any .py or .pxd

rm -f ubjson/*.c
for ext in ubjson/*.py; do
    # exclude module main so still works when using compiled extensions
    if [ "$ext" != "ubjson/__main__.py" ]; then
        echo "Generating code for ${ext}"
        python3 -mcython -a -3 -f --fast-fail -Werror -Wextra -o ${ext}3.c ${ext}
        python3 -mcython -a -2 -f --fast-fail -Werror -Wextra -o ${ext}2.c ${ext}
    fi
done
