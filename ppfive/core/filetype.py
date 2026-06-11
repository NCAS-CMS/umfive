from __future__ import annotations

import struct
import sys

from .models import FileTypeInfo


def _valid_um_word2(val):
    """Validity of the second FF word.

    :Parameters:

        val: `int`
            The second FF word.

    :Returns:

        `bool`
            `True` for a valid word, otherwise `False`.

    """
    return val in (1, 2, 4)


def _valid_pp_word1(val, word_size):
    """Validity of the PP first block control word (BCW)

    :Parameters:

        var: `int`
            The fist BCW.

        word_size: `int`
            The word size (``4`` or ``8``).

    :Returns:

        `bool`
            `True` for a valid word, otherwise `False`.

    """
    return val in (64 * word_size, 128 * word_size)


def _is_alternating_zeros_with_offset(vals, num_pairs, offset):
    """Whether a sequence has alternating zeros.

    :Parameters:

        vals: sequence of `int`
            A concentated sequence of pairs of integers.

         num_pairs: `int`
             The number of pairs to look at.

         offset: `int`
             The index at which to start looking for alternate zeros,
             either ``0`` or ``1``.

    :Returns:

        `bool`
            `True` if the first of each pair, starting at the offset,
            is zero, otherwise `False`.

    """
    for i in range(num_pairs):
        if vals[i * 2 + offset] != 0:
            return False

    return True


def _is_alternating_zeros(vals: list[int], num_pairs: int) -> bool:
    """Whether a sequence has alternating zeros.

    The zeros may start at index ``0`` or ``1``.

    :Parameters:

        vals: sequence of `int`
            A concentated sequence of pairs of integers.

         num_pairs: `int`
             The number of pairs to look at.

    :Returns:

        `bool`
            `True` if the first of each pair is zero, otherwise
            `False`.

    """
    if _is_alternating_zeros_with_offset(vals, num_pairs, 0):
        return True

    return _is_alternating_zeros_with_offset(vals, num_pairs, 1)


def _unpack_many(fmt, buf, offset, count):
    """Unpack a number of words from a byte string.

    :Parameters:

        fmt: `str`
            The word format to unpack into (e.g. ``'<i'``, ``'>i'``,
            ``'<q'``, ``'>q'``).

        buf: `bytes`
            The bytes to unpack. Only the bytes for the *count* number
            of wards are unpacked.

        offset: `int`

        count: `int`
            The number of words (each defined by *fmt*) to unpack.

    :Returns:

        `list`
            The list of unpacked words.

    """
    size = struct.calcsize(fmt)
    return [
        struct.unpack(fmt, buf[offset + i * size : offset + (i + 1) * size])[0]
        for i in range(count)
    ]


def detect_file_type(reader):
    """Auto-detect file type from initial bytes.

    :Parameters:

        reader: `ByteReader`
            The file reader.

    :Returns:

        `FileTypeInfo`
            A file-type information object.

    """
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
            byte_order="little" if native == "<" else "big",
            word_size=4,
        )

    if _valid_um_word2(data8[1]):
        return FileTypeInfo(
            fmt="FF",
            byte_order="little" if native == "<" else "big",
            word_size=8,
        )

    if _valid_um_word2(data4s[1]):
        return FileTypeInfo(
            fmt="FF",
            byte_order="big" if native == "<" else "little",
            word_size=4,
        )

    if _valid_um_word2(data8s[1]):
        return FileTypeInfo(
            fmt="FF",
            byte_order="big" if native == "<" else "little",
            word_size=8,
        )

    if _valid_pp_word1(data8[0], 8) and _is_alternating_zeros(data4, n_pairs):
        return FileTypeInfo(
            fmt="PP",
            byte_order="little" if native == "<" else "big",
            word_size=8,
        )

    if _valid_pp_word1(data8s[0], 8) and _is_alternating_zeros(data4, n_pairs):
        return FileTypeInfo(
            fmt="PP",
            byte_order="big" if native == "<" else "little",
            word_size=8,
        )

    if _valid_pp_word1(data4[0], 4):
        return FileTypeInfo(
            fmt="PP",
            byte_order="little" if native == "<" else "big",
            word_size=4,
        )

    if _valid_pp_word1(data4s[0], 4):
        return FileTypeInfo(
            fmt="PP",
            byte_order="big" if native == "<" else "little",
            word_size=4,
        )

    raise ValueError("File type could not be detected")
