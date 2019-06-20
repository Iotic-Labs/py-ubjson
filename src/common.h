/*
 * Copyright (c) 2019 Iotic Labs Ltd. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://github.com/Iotic-Labs/py-ubjson/blob/master/LICENSE
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#pragma once

#if defined (__cplusplus)
extern "C" {
#endif

/******************************************************************************/

#define MIN(x, y) (x) <= (y) ? (x) : (y)
#define MAX(x, y) (x) >= (y) ? (x) : (y)

#define UNUSED(x) (void)(x)

#define BAIL_ON_NULL(result)\
if (NULL == (result)) {\
    goto bail;\
}

#define BAIL_ON_NONZERO(result)\
if (result) {\
    goto bail;\
}

#define BAIL_ON_NEGATIVE(result)\
if ((result) < 0) {\
    goto bail;\
}

#if defined (__cplusplus)
}
#endif
