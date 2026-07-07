#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <numpy/arrayobject.h>

#include <errno.h>
#include <float.h>
#include <math.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define I32_INFP 0x7f800000
#define I32_INFN 0xff800000
#define I32_ZEROP 0x00000000
#define I32_ZERON 0x80000000

typedef float float32_t;
typedef double float64_t;

typedef enum { little_endian, big_endian } Byte_ordering;

#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
#define NATIVE_ORDERING big_endian
#else
#define NATIVE_ORDERING little_endian
#endif

static _Thread_local char last_error[512] = {0};

static void error_mesg(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    vsnprintf(last_error, sizeof(last_error), fmt, args);
    va_end(args);
}

static void swap_bytes_sgl(void *ptr, size_t num_words)
{
    size_t i;
    char *p = (char *)ptr;
    char t;
    for (i = 0; i < num_words; i++) {
        t = p[3]; p[3] = p[0]; p[0] = t;
        t = p[2]; p[2] = p[1]; p[1] = t;
        p += 4;
    }
}

static void swap_bytes_dbl(void *ptr, size_t num_words)
{
    size_t i;
    char *p = (char *)ptr;
    char t;
    for (i = 0; i < num_words; i++) {
        t = p[7]; p[7] = p[0]; p[0] = t;
        t = p[6]; p[6] = p[1]; p[1] = t;
        t = p[5]; p[5] = p[2]; p[2] = t;
        t = p[4]; p[4] = p[3]; p[3] = t;
        p += 8;
    }
}

static int bit_test_value(void *iword, int ibit)
{
    unsigned int ui = *(unsigned int *)iword;
    return ((ui >> ibit) & 1U) ? 1 : 0;
}

static void move_bits_value(void *word1, int start1, int nbits, void *word2)
{
    uint32_t *ui1 = (uint32_t *)word1;
    uint32_t *ui2 = (uint32_t *)word2;
    if (start1 + 1 - nbits >= 0) {
        ui2[0] = (ui1[0] >> (start1 + 1 - nbits)) & ~(~0U << nbits);
    } else {
        uint32_t temp1 = (ui1[0] << (nbits - start1 - 1)) & ~(~0U << nbits);
        uint32_t temp2 = (ui1[1] >> (32 + start1 + 1 - nbits)) & ~(~0U << (nbits - start1 - 1));
        ui2[0] = temp1 | temp2;
    }
}

static float32_t get_float32_value(void *in)
{
    unsigned char *pin = (unsigned char *)in;
    unsigned long man = ((unsigned long)pin[1] << 16) |
                        ((unsigned long)pin[2] << 8) |
                        (unsigned long)pin[3];
    int exp = pin[0] & 0x7f;
    int sign = pin[0] & 0x80;
    double d = ldexp((double)man, 4 * (exp - 64 - 6));
    union {
        uint32_t u;
        float32_t f;
    } cast_value;

    if (d > (double)FLT_MAX || errno == ERANGE) {
        cast_value.u = sign ? I32_INFN : I32_INFP;
        return cast_value.f;
    }
    if (d < (double)FLT_MIN) {
        cast_value.u = sign ? I32_ZERON : I32_ZEROP;
        return cast_value.f;
    }
    return sign ? (float32_t)-d : (float32_t)d;
}

static int16_t get_int16_value(void *start, Byte_ordering byte_ordering)
{
    if (byte_ordering == NATIVE_ORDERING) {
        return *(int16_t *)start;
    }

    char *in = (char *)start;
    char out[2];
    out[0] = in[1];
    out[1] = in[0];
    return *(int16_t *)out;
}

static int32_t get_int32_value(void *start, Byte_ordering byte_ordering)
{
    if (byte_ordering == NATIVE_ORDERING) {
        return *(int32_t *)start;
    }

    char *in = (char *)start;
    char out[4];
    out[0] = in[3];
    out[1] = in[2];
    out[2] = in[1];
    out[3] = in[0];
    return *(int32_t *)out;
}

#define WG_JOIN_INNER(a, b) a##_##b
#define WG_JOIN(a, b) WG_JOIN_INNER(a, b)

#define WG_NAME(name) WG_JOIN(name, sgl)
#define WG_REAL float32_t
#define WG_WORD_SIZE 4
#define WG_SWAP_BYTES swap_bytes_sgl
#include "wgdos_impl.h"
#undef WG_NAME
#undef WG_REAL
#undef WG_WORD_SIZE
#undef WG_SWAP_BYTES

#define WG_NAME(name) WG_JOIN(name, dbl)
#define WG_REAL float64_t
#define WG_WORD_SIZE 8
#define WG_SWAP_BYTES swap_bytes_dbl
#include "wgdos_impl.h"
#undef WG_NAME
#undef WG_REAL
#undef WG_WORD_SIZE
#undef WG_SWAP_BYTES
#undef WG_JOIN
#undef WG_JOIN_INNER

static PyObject *py_unwgdos(PyObject *self, PyObject *args)
{
    Py_buffer input_view;
    int nout;
    double mdi;
    int word_size;
    char *input_copy = NULL;
    PyObject *array = NULL;
    int status;
    npy_intp dims[1];
    Py_ssize_t input_len;

    (void)self;
    last_error[0] = '\0';

    if (!PyArg_ParseTuple(args, "y*idi", &input_view, &nout, &mdi, &word_size)) {
        return NULL;
    }

    if (word_size != 4 && word_size != 8) {
        PyBuffer_Release(&input_view);
        PyErr_SetString(PyExc_ValueError, "word_size must be 4 or 8");
        return NULL;
    }

    if (nout < 0) {
        PyBuffer_Release(&input_view);
        PyErr_SetString(PyExc_ValueError, "nout must be >= 0");
        return NULL;
    }

    input_len = input_view.len;
    input_copy = PyMem_Malloc((size_t)input_len);
    if (input_copy == NULL) {
        PyBuffer_Release(&input_view);
        return PyErr_NoMemory();
    }
    memcpy(input_copy, input_view.buf, (size_t)input_len);
    PyBuffer_Release(&input_view);

    dims[0] = (npy_intp)nout;
    array = PyArray_SimpleNew(1, dims, word_size == 4 ? NPY_FLOAT32 : NPY_FLOAT64);
    if (array == NULL) {
        PyMem_Free(input_copy);
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS
    if (word_size == 4) {
        status = unwgdos_sgl(input_copy, (int)input_len, (float32_t *)PyArray_DATA((PyArrayObject *)array), nout, (float32_t)mdi);
    } else {
        status = unwgdos_dbl(input_copy, (int)input_len, (float64_t *)PyArray_DATA((PyArrayObject *)array), nout, (float64_t)mdi);
    }
    Py_END_ALLOW_THREADS

    PyMem_Free(input_copy);

    if (status != 0) {
        Py_DECREF(array);
        PyErr_SetString(PyExc_RuntimeError, last_error[0] ? last_error : "WGDOS decode failed");
        return NULL;
    }

    return array;
}

static PyMethodDef wgdos_methods[] = {
    {"unwgdos", py_unwgdos, METH_VARARGS, "Decode WGDOS packed bytes into a NumPy array."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef wgdos_module = {
    PyModuleDef_HEAD_INIT,
    "_wgdos",
    NULL,
    -1,
    wgdos_methods,
};

PyMODINIT_FUNC PyInit__wgdos(void)
{
    import_array();
    return PyModule_Create(&wgdos_module);
}
