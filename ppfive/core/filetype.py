from __future__ import annotations

import struct
import sys

from ppfive.io.base import ByteReader

from .models import FileTypeInfo


def _valid_um_word2(val: int) -> bool:
    """TODO."""
    return val in (1, 2, 4)


def _valid_pp_word1(val: int, wsize: int) -> bool:
    """TODO."""
    return val in (64 * wsize, 128 * wsize)


def _is_alternating_zeros_without_offset(
    vals: list[int], num_pairs: int
) -> bool:
    """TODO."""
    for i in range(num_pairs):
        if vals[i * 2] != 0:
            return False
    return True


def _is_alternating_zeros(vals: list[int], num_pairs: int) -> bool:
    """TODO."""
    if _is_alternating_zeros_without_offset(vals, num_pairs):
        return True

    for i in range(num_pairs):
        if vals[(i * 2) + 1] != 0:
            return False
    return True


def _unpack_many(fmt: str, buf: bytes, offset: int, count: int) -> list[int]:
    """TODO."""
    size = struct.calcsize(fmt)
    return [
        struct.unpack(fmt, buf[offset + i * size : offset + (i + 1) * size])[0]
        for i in range(count)
    ]


def detect_file_type(reader: ByteReader) -> FileTypeInfo:
    """Auto-detect file type from initial bytes, mirroring C logic."""
    n_pairs = 14
    raw = reader.read_at(0, 8 * n_pairs)
    if len(raw) < 8 * n_pairs:
        raise ValueError("Insufficient bytes to detect file type")

    native = "<" if sys.byteorder == "little" else ">"
    reverse = ">" if native == "<" else "<"

    data4 = _unpack_many(f"{native}i", raw, 0, 2 * n_pairs)
    data4s = _unpack_many(f"{reverse}i", raw, 0, 2)
    data8 = _unpack_many(f"{native}q", raw, 0, 2)
    data8s = _unpack_many(f"{reverse}q", raw, 0, 2)

    if _valid_um_word2(data4[1]):
        return FileTypeInfo(
            fmt="FF",
            byte_ordering="little_endian" if native == "<" else "big_endian",
            word_size=4,
        )
    if _valid_um_word2(data8[1]):
        return FileTypeInfo(
            fmt="FF",
            byte_ordering="little_endian" if native == "<" else "big_endian",
            word_size=8,
        )
    if _valid_um_word2(data4s[1]):
        return FileTypeInfo(
            fmt="FF",
            byte_ordering="big_endian" if native == "<" else "little_endian",
            word_size=4,
        )
    if _valid_um_word2(data8s[1]):
        return FileTypeInfo(
            fmt="FF",
            byte_ordering="big_endian" if native == "<" else "little_endian",
            word_size=8,
        )

    if _valid_pp_word1(data8[0], 8) and _is_alternating_zeros(data4, n_pairs):
        return FileTypeInfo(
            fmt="PP",
            byte_ordering="little_endian" if native == "<" else "big_endian",
            word_size=8,
        )
    if _valid_pp_word1(data8s[0], 8) and _is_alternating_zeros(data4, n_pairs):
        return FileTypeInfo(
            fmt="PP",
            byte_ordering="big_endian" if native == "<" else "little_endian",
            word_size=8,
        )
    if _valid_pp_word1(data4[0], 4):
        return FileTypeInfo(
            fmt="PP",
            byte_ordering="little_endian" if native == "<" else "big_endian",
            word_size=4,
        )
    if _valid_pp_word1(data4s[0], 4):
        return FileTypeInfo(
            fmt="PP",
            byte_ordering="big_endian" if native == "<" else "little_endian",
            word_size=4,
        )

    raise ValueError("File type could not be detected")
