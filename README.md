# Overview

This is a Python v3.2+ (and 2.7+) [Universal Binary JSON](http://ubjson.org) encoder/decoder based on the [draft-12](UBJSON-Specification.md) specification.


# Installing / packaging
```shell
# To get from PyPI
pip3 install py-ubjson

# To only build extension modules inline (e.g. in repository)
python3 setup.py build_ext -i

# To build & install globally
python3 setup.py install

# To skip building of extensions when installing (or building)
PYUBJSON_NO_EXTENSION=1 python3 setup.py install
```
**Notes**

- The ([cython](http://cython.org)-generated) extension modules are not required but provide a significant speed boost.
- The above can also be run with v2.7+
- PyPI releases are signed with the [Iotic Labs Software release signing key](https://iotic-labs.com/iotic-labs.com.asc)
- If any _.py_ or _.pxd_ has been modified, _cython_generate.sh_ has to be run first
- At run time, one can check whether compiled version is in use via the _ubjson.EXTENSION_ENABLED_ boolean


# Usage
It's meant to behave very much like Python's built-in [JSON module](https://docs.python.org/3/library/json.html), e.g.:
```python
import ubjson

encoded = ubjson.dumpb({u'a': 1})

decoded = ubjson.loadb(encoded)
```
**Note**: Only unicode strings in Python 2 will be encoded as strings, plain *str* will be encoded as a byte array.


# Documentation
```python
import ubsjon
help(ubjson.dump)
help(ubjson.load)
```

# Command-line utility
This converts between JSON and UBJSON formats:
```shell
python3 -mubjson
USAGE: ubjson (fromjson|tojson) (INFILE|-) [OUTFILE]
```


# Tests

## Static
This library has been checked using [flake8](https://pypi.python.org/pypi/flake8) and [pylint](http://www.pylint.org), using a modified configuration - see _pylint.rc_ and _flake8.cfg_.

## Unit
```shell
./coverage_test.sh
```
**Note**: This requires [coverage](https://pypi.python.org/pypi/coverage).


# Limitations
- The **No-Op** type is not supported. (This should arguably be a protocol-level rather than serialisation-level option.)
- Strongly-typed containers are only supported by the decoder (apart from for **bytes**/**bytearray**).
- Encoder/decoder extensions are not supported at this time.
- cython optimizations could be improved.


# Why?
The only existing implementation I was aware of at the time of writing ([simpleubjson](https://github.com/brainwater/simpleubjson)) had the following limitations:

- Does not support efficient binary encoding
- Only supports draft-9
- Only supports individual Python types rather than anything implementing an interface (e.g. _Mapping_)
- Does not decode nested arrays or objects in expected form
- Lacks C extension speed-up
