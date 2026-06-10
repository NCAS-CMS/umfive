from __future__ import annotations

import numpy as np

from ppfive.io.bytereader import ByteReader

from ..constants import N_HDR, N_INT_HDR, N_REAL_HDR


def _endian_prefix(byte_order: str) -> str:
    """TODO."""
    if byte_order == "little":
        return "<"

    if byte_order == "big":
        return ">"

    raise ValueError(f"Unsupported byte_order: {byte_order!r}")


def _int_dtype(word_size: int, byte_order: str):
    """TODO."""
    prefix = _endian_prefix(byte_order)
    if word_size == 4:
        return np.dtype(f"{prefix}i4")

    if word_size == 8:
        return np.dtype(f"{prefix}i8")

    raise ValueError(f"Unsupported word_size: {word_size!r}")


def _real_dtype(word_size: int, byte_order: str):
    """TODO."""
    prefix = _endian_prefix(byte_order)
    if word_size == 4:
        return np.dtype(f"{prefix}f4")

    if word_size == 8:
        return np.dtype(f"{prefix}f8")

    raise ValueError(f"Unsupported word_size: {word_size!r}")


def decode_header_from_bytes(
    header_bytes: bytes, word_size: int, byte_order: str
):
    """TODO."""
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


def read_header(
    reader: ByteReader, header_offset: int, word_size: int, byte_order: str
):
    """TODO."""
    header_bytes = reader.read_at(header_offset, N_HDR * word_size)
    return decode_header_from_bytes(header_bytes, word_size, byte_order)
