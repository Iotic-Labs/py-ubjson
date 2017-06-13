# Index
- [Introduction](#introduction)
- [License](#license)
- [Draft 12 specification](#draft12)
  - [Data Format](#data_format)
  - [Type overview](#type_overview)
  - [Value types](#value_types)
  - [Container types](#container_types)
  - [Optimized format](#container_optimized)


# <a name="introduction"/>Introduction
For the official, most up-to-date, more verbose specification (with discussion and examples) of Universal Binary JSON please visit [ubjson.org](http://ubjson.org). Since at the time of writing (6th August 2015) neither said website nor the [community workspace git repository](https://github.com/thebuzzmedia/universal-binary-json) indicated what version the specification applies to, I made the decision to produce this minimal document to act as a reference in case the specification on ubjson.org changes. I contacted Riyad Kalla of [The Buzz Media](http://www.thebuzzmedia.com) (and maintainer of ubjson.org) and he confirmed to me that (at said point in time) the current version was indeed Draft 12.


# <a name="license"/>License
The UBJSON Specification is licensed under the [Apache 2.0 License](http://www.apache.org/licenses/LICENSE-2.0.html).


# <a name="draft12"/>Draft 12 specification


## <a name="data_format"/>Data Format

A single construct with two optional segments (length and data) is used for all types:
```
[type, 1 byte char]([integer numeric length])([data])
```
Each element in the tuple is defined as:
- **type** - A 1 byte ASCII char (**_Marker_**) used to indicate the type of the data following it.

- **length** (_optional_) - A positive, integer numeric type (uint8, int16, int32, int64) specifying the length of the following data payload.

- **data** (_optional_) - A run of bytes representing the actual binary data for this type of value.

### Notes
- Some values are simple enough that just writing the 1 byte ASCII marker into the stream is enough to represent the value (e.g. null) while others have a type that is specific enough that no length is needed as the length is implied by the type (e.g. int32) while others still require both a type and a length to communicate their value (e.g. string). Additionally some values (e.g. array) have additional (_optional_) parameters to improve decoding efficiency and/or to reduce size of the encoded value even further.

- The UBJSON specification requires that all numeric values be written in Big-Endian order.

- To store binary data, use a [strongly-typed](#container_optimized) array of uint8 values.

- _application/ubjson_ should be used as the mime type

- _.ubj_ should be used a the file extension when storing UBJSON-encoded data is saved to a file

## <a name="type_overview"/>Type overview

Type | Total size | ASCII Marker(s) | Length required | Data (payload)
---|---|---|---|---
[null](#value_null) | 1 byte | *Z* | No | No
[no-op](#value_noop) | 1 byte | *N* | No | No
[true](#value_bool) | 1 byte | *T* | No | No
[false](#value_bool) | 1 byte | *F* | No | No
[int8](#value_numeric) | 2 bytes | *i* | No | Yes
[uint8](#value_numeric) | 2 bytes | *U* | No | Yes
[int16](#value_numeric) | 3 bytes | *I* (upper case i) | No | Yes
[int32](#value_numeric) | 5 bytes | *l* (lower case L) | No | Yes
[int64](#value_numeric) | 9 bytes | *L* | No | Yes
[float32](#value_numeric) | 5 bytes | *d* | No | Yes
[float64](#value_numeric) | 9 bytes | *D* | No | Yes
[high-precision number](#value_numeric) | 1 byte + int num val + string byte len | *H* | Yes | Yes
[char](#value_char) | 2 bytes | *C* | No | Yes
[string](#value_string) | 1 byte + int num val + string byte len | *S* | Yes | Yes (if not empty)
[array](#container_array) | 2+ bytes | *\[* and *\]* | Optional | Yes (if not empty)
[object](#container_object) | 2+ bytes | *{* and *}* | Optional | Yes (if not empty)


## <a name="value_types"/>Value Types

### <a name="value_null"/>Null
The null value in is equivalent to the null value from the JSON specification.

#### Example
In JSON:
```json
{
    "passcode": null
}
```

In UBJSON (using block-notation):
```
[{]
    [i][8][passcode][Z]
[}]
```

---
### <a name="value_noop"/>No-Op
There is no equivalent to no-op value in the original JSON specification. When decoding, No-Op values should be skipped. Also, they can only occur as elements of a container.

---
### <a name="value_bool"/>Boolean
A boolean type is is equivalent to the boolean value from the JSON specification.

#### Example
In JSON:
```json
{
    "authorized": true,
    "verified": false
}
```

In UBJSON (using block-notation):
```
[{]
    [i][10][authorized][T]
    [i][8][verified][F]
[}]
```

---
### <a name="value_numeric"/>Numeric
Unlike in JSON whith has a single _Number_ type (used for both integers and floating point numbers), UBJSON defines multiple types for integers. The minimum/maximum of values (inclusive) for each integer type are as follows:

Type | Signed | Minimum | Maximum
---|---|---|---
int8 | Yes | -128 | 127
uint8 | No | 0 | 255
int16 | Yes | -32,768 | 32,767
int32 | Yes | -2,147,483,648 | 2,147,483,647
int64 | Yes | -9,223,372,036,854,775,808 | 9,223,372,036,854,775,807
float32 | Yes | See [IEEE 754 Spec](http://en.wikipedia.org/wiki/IEEE_754-1985) | See [IEEE 754 Spec](https://en.wikipedia.org/wiki/IEEE_754-1985)
float64 | Yes | See [IEEE 754 Spec](http://en.wikipedia.org/wiki/IEEE_754-1985) | See [IEEE 754 Spec](https://en.wikipedia.org/wiki/IEEE_754-1985)
high-precision number | Yes | Infinite | Infinite

**Notes**:
- Numeric values of infinity (and NaN) are to be encoded as a [null](#value_null) in all cases
- It is advisable to use the smallest applicable type when encoding a number.

#### Integer
All integer types are written in Big-Endian order.

#### Float
- float32 values are written in [IEEE 754 single precision floating point format](http://en.wikipedia.org/wiki/IEEE_754-1985), which has the following structure:
  - Bit 31 (1 bit) - sign
  - Bit 30-23 (8 bits) - exponent
  - Bit 22-0 (23 bits) - fraction (significant)

- float64 values are written in [IEEE 754 double precision floating point format](http://en.wikipedia.org/wiki/IEEE_754-1985), which has the following structure:
  - Bit 63 (1 bit) - sign
  - Bit 62-52 (11 bits) - exponent
  - Bit 51-0 (52 bits) - fraction (significant)

#### High-Precision
These are encoded as a string and thus are only limited by the maximum string size. Values **must** be written out in accordance with the original [JSON number type specification](http://json.org). Infinity (and NaN) are to be encoded as a [null](#value_null) value.

#### Examples
Numeric values in JSON:
```json
{
    "int8": 16,
    "uint8": 255,
    "int16": 32767,
    "int32": 2147483647,
    "int64": 9223372036854775807,
    "float32": 3.14,
    "float64": 113243.7863123,
    "huge1": "3.14159265358979323846",
    "huge2": "-1.93+E190",
    "huge3": "719..."
}
```

In UBJSON (using block-notation):
```
[{]
    [i][4][int8][i][16]
    [i][5][uint8][U][255]
    [i][5][int16][I]32767]
    [i][5][int32][l][2147483647]
    [i][5][int64][L][9223372036854775807]
    [i][7][float32][d][3.14]
    [i][7][float64][D][113243.7863123]
    [i][5][huge1][H][i][22][3.14159265358979323846]
    [i][5][huge2][H][i][10][-1.93+E190]
    [i][5][huge3][H][U][200][719...]
[}]
```

---
### <a name="value_char"/>Char
The char type in UBJSON is an unsigned byte meant to represent a single printable ASCII character (decimal values 0-127). It **must not** have a decimal value larger than 127. It is functionally identical to the uint8 type, but semantically is meant to represent a character and not a numeric value.

#### Example
Char values in JSON:
```json
{
    "rolecode": "a",
    "delim": ";",
}
```

UBJSON (using block-notation):
```
[{]
    [i][8][rolecode][C][a]
    [i][5][delim][C][;]
[}]
```

---
### <a name="value_string"/>String
The string type in UBJSON is equivalent to the string type from the JSON specification apart from that the UBJSON string value **requires** UTF-8 encoding.

#### Example
String values in JSON:
```json
{
    "username": "rkalla",
    "imagedata": "...huge string payload..."
}
```

UBJSON (using block-notation):
```
[{]
    [i][8][username][S][i][5][rkalla]
    [i][9][imagedata][S][l][2097152][...huge string payload...]
[}]
```


## <a name="container_types"/>Container types
See also [optimized format](#container_optimized) below.

### <a name="container_array"/>Array
The array type in UBJSON is equivalent to the array type from the JSON specification.

#### Example
Array in JSON:
```json
[
    null,
    true,
    false,
    4782345193,
    153.132,
    "ham"
]
```

UBJSON (using block-notation):
```
[[]
    [Z]
    [T]
    [F]
    [l][4782345193]
    [d][153.132]
    [S][i][3][ham]
[]]
```

---
### <a name="container_object"/>Object
The object type in UBJSON is equivalent to the object type from the JSON specification. Since value names can only be strings, the *S* (string) marker **must not** be included since it is redundant.

#### Example

Object in JSON:
```json
{
    "post": {
        "id": 1137,
        "author": "rkalla",
        "timestamp": 1364482090592,
        "body": "I totally agree!"
    }
}
```

UBJSON (using block-notation):
```
[{]
    [i][4][post][{]
        [i][2][id][I][1137]
        [i][6][author][S][i][5][rkalla]
        [i][9][timestamp][L][1364482090592]
        [i][4][body][S][i][16][I totally agree!]
    [}]
[}]
```

## <a name="container_optimized"/>Optimized Format
Both container types support optional parameters that can help optimize the container for better parsing performance and smaller size.

### Type - *$*
When a _type_ is specified, all value types stored in the container (either array or object) are considered to be of that singular _type_ and as a result, _type_ markers are omitted for each value within the container. This can be thought of providing the ability to create a strongly typed container in UBJSON.
- If a _type_ is specified, it **must** be done so before a _count_.
- If a _type_ is specified, a _count_ **must** be specified as well. (Otherwise it is impossible to tell when a container is ending, e.g. did you just parse *]* or the int8 value of 93?)

#### Example (string type):
```
[$][S]
```

---
### Count - *\#*
When a _count_ is specified, the parser is able to know ahead of time how many child elements will be parsed. This allows the parser to pre-size any internal construct used for parsing, verify that the promised number of child values were found and avoid scanning for any terminating bytes while parsing.
- A _count_ can be specified without a type.

#### Example (count of 64):
```
[#][i][64]
```

### Additional rules
- A _count_ **must** be >= 0.
- A _count_ can be specified by itself.
- If a _count_ is specified the container **must not** specify an end-marker.
- A container that specifies a _count_ **must** contain the specified number of child elements.
- If a _type_ is specified, it **must** be done so before count.
- If a _type_ is specified, a _count_ **must** also be specified. A _type_ cannot be specified by itself.
- A container that specifies a _type_ **must not** contain any additional _type_ markers for any contained value.

---
### Array Examples
Optimized with count
```
[[][#][i][5] // An array of 5 elements.
    [d][29.97]
    [d][31.13]
    [d][67.0]
    [d][2.113]
    [d][23.8889]
// No end marker since a count was specified.
```
Optimized with type & count
```
[[][$][d][#][i][5] // An array of 5 float32 elements.
    [29.97] // Value type is known, so type markers are omitted.
    [31.13]
    [67.0]
    [2.113]
    [23.8889]
// No end marker since a count was specified.
```

---
### Object Examples
Optimized with count
```
[{][#][i][3] // An object of 3 name:value pairs.
    [i][3][lat][d][29.976]
    [i][4][long][d][31.131]
    [i][3][alt][d][67.0]
// No end marker since a count was specified.
```
Optimized with type & count
```
[{][$][d][#][i][3] // An object of 3 name:float32-value pairs.
    [i][3][lat][29.976] // Value type is known, so type markers are omitted.
    [i][4][long][31.131]
    [i][3][alt][67.0]
// No end marker since a count was specified.
```

---
### Special case: Marker-only types (null, no-op & boolean)
If using both _count_ and _type_ optimisations, the marker itself represent the value thus saving repetition (since these types to not have a payload). Additional requirements are:

Strongly typed array of type true (boolean) and with a count of 512:
```
[[][$][T][#][I][512]
```

Strongly typed object of type null and with a count of 3:
```
[{][$][Z][#][i][3]
    [i][4][name] // name only, no value specified.
    [i][8][password]
    [i][5][email]
```
