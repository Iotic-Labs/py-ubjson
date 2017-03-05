/*
 * Copyright (c) 2001-2016 Python Software Foundation; All Rights Reserved
 *
 * Licensed under PSF license, see: https://docs.python.org/3/license.html
 *
 * Herein are a selection of functions which are not part of Python's public
 * C-API, including some of floatobject.c
 */

#pragma once

#if defined (__cplusplus)
extern "C" {
#endif


/******************************************************************************/

/* MUST be called before using floating point related functions defined below */
extern void _pyfuncs_ubj_detect_formats(void);

/* _PyFloat_{Pack,Unpack}{4,8}
 *
 * The struct and pickle (at least) modules need an efficient platform-
 * independent way to store floating-point values as byte strings.
 * The Pack routines produce a string from a C double, and the Unpack
 * routines produce a C double from such a string.  The suffix (4 or 8)
 * specifies the number of bytes in the string.
 *
 * On platforms that appear to use (see _PyFloat_Init()) IEEE-754 formats
 * these functions work by copying bits.  On other platforms, the formats the
 * 4- byte format is identical to the IEEE-754 single precision format, and
 * the 8-byte format to the IEEE-754 double precision format, although the
 * packing of INFs and NaNs (if such things exist on the platform) isn't
 * handled correctly, and attempting to unpack a string containing an IEEE
 * INF or NaN will raise an exception.
 *
 * On non-IEEE platforms with more precision, or larger dynamic range, than
 * 754 supports, not all values can be packed; on non-IEEE platforms with less
 * precision, or smaller dynamic range, not all values can be unpacked.  What
 * happens in such cases is partly accidental (alas).
 */

/* The pack routines write 2, 4 or 8 bytes, starting at p.  le is a bool
 * argument, true if you want the string in little-endian format (exponent
 * last, at p+1, p+3 or p+7), false if you want big-endian format (exponent
 * first, at p).
 * Return value:  0 if all is OK, -1 if error (and an exception is
 * set, most likely OverflowError).
 * There are two problems on non-IEEE platforms:
 * 1):  What this does is undefined if x is a NaN or infinity.
 * 2):  -0.0 and +0.0 produce the same string.
 */
extern int _pyfuncs_ubj_PyFloat_Pack4(double x, unsigned char *p, int le);
extern int _pyfuncs_ubj_PyFloat_Pack8(double x, unsigned char *p, int le);
extern double _pyfuncs_ubj_PyFloat_Unpack4(const unsigned char *p, int le);
extern double _pyfuncs_ubj_PyFloat_Unpack8(const unsigned char *p, int le);

#ifdef __cplusplus
}
#endif
