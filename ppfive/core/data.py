from __future__ import annotations

import numpy as np

from ppfive.io.base import ByteReader

from ..constants import INDEX_BMDI, INDEX_LBPACK
from ..wgdos import unpack_wgdos
from .interpret import get_extra_data_length, get_type_and_num_words
from .models import RecordInfo


def _endian_prefix(byte_order: str) -> str:
    """TODO."""
    if byte_order == "little":
        return "<"

    if byte_order == "big":
        return ">"

    raise ValueError(f"Unsupported byte_order: {byte_order!r}")


def _dtype_for_record(
    rec: RecordInfo, word_size: int, byte_order: str
) -> np.dtype:
    """TODO."""
    data_type, _ = get_type_and_num_words(rec.int_hdr, word_size)
    prefix = _endian_prefix(byte_order)
    if data_type == "integer":
        return np.dtype(f"{prefix}i{word_size}")

    return np.dtype(f"{prefix}f{word_size}")


def _unpack_cray32(
    raw: bytes, nwords: int, byte_order: str, word_size: int
) -> np.ndarray:
    """TODO."""
    prefix = _endian_prefix(byte_order)
    packed = np.frombuffer(
        raw[: nwords * 4], dtype=np.dtype(f"{prefix}f4"), count=nwords
    )
    if word_size == 4:
        return packed.astype(np.float32, copy=True)

    return packed.astype(np.float64, copy=True)


def _unpack_run_length(
    raw: bytes, nwords: int, byte_order: str, word_size: int, mdi: float
) -> np.ndarray:
    """Unpack runlength encoded data.

    :Parameters:

        raw: bytes
            The raw bytes of the packed data.

        nwords: `int`
            The number of words in the unpacked data.

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

        word_size: `int`
            The word size (``4`` or ``8``).

        mdi: `float`
            The missing data value.

    :Returns:

        `np.ndarray`
            The unpacked data in a 1-d array.

    """
    prefix = _endian_prefix(byte_order)
    dtype = np.dtype(f"{prefix}f{word_size}")
    packed = np.frombuffer(raw, dtype=dtype)
    # out = np.empty(nwords, dtype=np.float32 if word_size == 4 else np.float64)
    out = np.full((nwords,), mdi, dtype=f"f{word_size}")

    src = 0
    dst = 0
    while src < packed.size and dst < nwords:
        value = packed[src]
        src += 1
        if value != mdi:
            out[dst] = value
            dst += 1
            continue

        if src >= packed.size:
            raise ValueError(
                "Malformed run-length packed data: truncated repeat count"
            )

        repeat = int(0.5 + float(packed[src]))
        src += 1
        if repeat < 0:
            raise ValueError(
                "Malformed run-length packed data: negative repeat count"
            )

        end = dst + repeat
        if end > nwords:
            raise ValueError(
                "Malformed run-length packed data: repeat exceeds output size"
            )

        # out[dst:end] = mdi
        dst = end

    if dst != nwords:
        raise ValueError(
            "Malformed run-length packed data: output size mismatch"
        )

    return out


def get_record_packed_nbytes(rec: RecordInfo, word_size: int) -> int:
    """TODO."""
    extra_bytes = get_extra_data_length(rec.int_hdr, word_size)
    return rec.disk_length - extra_bytes


def read_record_raw(
    reader: ByteReader, rec: RecordInfo, word_size: int
) -> bytes:
    """TODO."""
    packed_bytes = get_record_packed_nbytes(rec, word_size)
    raw = reader.read_at(rec.data_offset, packed_bytes)
    if len(raw) < packed_bytes:
        raise ValueError("Short read while loading raw record bytes")

    return raw


def decode_record_array_from_raw(
    raw: bytes, rec: RecordInfo, word_size: int, byte_order: str
) -> np.ndarray:
    """TODO."""
    pack = int(rec.int_hdr[INDEX_LBPACK]) % 10
    _, nwords = get_type_and_num_words(rec.int_hdr, word_size)

    if pack == 0:
        need = nwords * word_size
        dtype = _dtype_for_record(rec, word_size, byte_order)
        return np.frombuffer(raw[:need], dtype=dtype, count=nwords).copy()

    if pack == 1:
        mdi = float(rec.real_hdr[INDEX_BMDI])
        return unpack_wgdos(raw, nwords, mdi, word_size)

    if pack == 2:
        return _unpack_cray32(raw, nwords, byte_order, word_size)

    if pack == 4:
        mdi = float(rec.real_hdr[INDEX_BMDI])
        return _unpack_run_length(raw, nwords, byte_order, word_size, mdi)

    if pack == 3:
        raise NotImplementedError("GRIB packed data is not supported")

    raise NotImplementedError(
        f"Packed data mode {pack} is not implemented yet"
    )


def read_record_array(
    reader: ByteReader, rec: RecordInfo, word_size: int, byte_order: str
) -> np.ndarray:
    """TODO."""
    raw = read_record_raw(reader, rec, word_size)
    return decode_record_array_from_raw(raw, rec, word_size, byte_order)
