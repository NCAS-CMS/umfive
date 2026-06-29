import numpy as np

from ..constants import N_HDR, N_INT_HDR, N_REAL_HDR


def endian_prefix(byte_order):
    """Return the '>' or '<' prefix for the byte_order.

    :Parameter:

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

    :Returns:

        `str`

    """
    if byte_order == "little":
        return "<"

    if byte_order == "big":
        return ">"

    raise ValueError(f"Unsupported byte_order: {byte_order!r}")


def _int_dtype(word_size, byte_order):
    """Return an integer real numpy.dtype`.

    :Parameter:

        word_size: `int`
            The word size (``4`` or ``8``).

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

    :Returns:

        `numpy.dtype

    """
    prefix = endian_prefix(byte_order)
    if word_size == 4:
        return np.dtype(f"{prefix}i4")

    if word_size == 8:
        return np.dtype(f"{prefix}i8")

    raise ValueError(f"Unsupported word_size: {word_size!r}")


def _real_dtype(word_size, byte_order):
    """Return a real numpy.dtype`.

    :Parameter:

        word_size: `int`
            The word size (``4`` or ``8``).

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

    :Returns:

        `numpy.dtype`

    """
    prefix = endian_prefix(byte_order)
    if word_size == 4:
        return np.dtype(f"{prefix}f4")

    if word_size == 8:
        return np.dtype(f"{prefix}f8")

    raise ValueError(f"Unsupported word_size: {word_size!r}")


def decode_header_from_bytes(header_bytes, word_size, byte_order):
    """Decode lookup header bytes into `numpy` arrays.

    :Parameter:

        header_bytes: `bytes`
            The raw bytes of the lookup header.

        word_size: `int`
            The word size (``4`` or ``8``).

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

    :Returns:

        `numpy.ndarray`, `numpy.ndarray`
            The integer and real lookup header arrays.

    """
    expected = N_HDR * word_size
    if len(header_bytes) < expected:
        raise ValueError("Header bytes shorter than required 64-word header")

    int_nbytes = N_INT_HDR * word_size
    int_hdr = np.frombuffer(
        header_bytes[:int_nbytes],
        dtype=_int_dtype(word_size, byte_order),
        count=N_INT_HDR,
    ).copy()
    real_hdr = np.frombuffer(
        header_bytes[int_nbytes:expected],
        dtype=_real_dtype(word_size, byte_order),
        count=N_REAL_HDR,
    ).copy()
    return int_hdr, real_hdr


def read_header(reader, header_offset, word_size, byte_order):
    """Read a lookup header into `numpy` arrays.

    :Parameters:

        reader: `ByteReader`
            The file reader.

        header_offset: `int`
            The byte address of the start of the integer header in the
            file.

        word_size: `int`
            The word size (``4`` or ``8``).

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

    :Returns:

        `numpy.ndarray`, `numpy.ndarray`
            The integer and real lookup header arrays.

    """
    header_bytes = reader.read_at(header_offset, N_HDR * word_size)
    return decode_header_from_bytes(header_bytes, word_size, byte_order)
