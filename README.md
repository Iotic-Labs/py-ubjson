# Overview

This is a non-recursive Python v3.x (and 2.7+) [Universal Binary JSON](http://ubjson.org) encoder/decoder based on the [[draft-12|UBJSON-Specification]] specification.

# Usage
It is meant to be usable like Python's built-in JSON module, e.g.:
```python
import ubjson

encoded = ubjson.dumpb({'a': 1})

decoded = ubjson.loadb(encoded)
```

# Documentation
```python
import ubsjon
help(ubjson.dump)
help(ubjson.load)
```

# Tests
```bash
# can also be run with Python v2
python3 -munittest discover ubjson
```

# Limitations
- The **No-Op** type is not supported. (This should arguably be a protocol-level rather than serialisation-level option.)
- Strongly-typed containers are only supported by the decoder (apart from for **bytes**/**bytearray**).
- Encoder/decoder extensions are not supported at this time.

# Why?
The only existing implementation I was aware of at the time of writing ([simpleubjson](https://github.com/brainwater/simpleubjson)) had the following limitations:
- Uses recursive encoding/decoding
- Does not support efficient binary encoding
- Only supports draft-9
- Only supports individual Python types rather than anything implementing an interface (e.g. _Mapping_)
