from __future__ import annotations

from ..constants import (
    INDEX_LBEXT,
    INDEX_LBLREC,
    INDEX_LBNPT,
    INDEX_LBNREC,
    INDEX_LBPACK,
    INDEX_LBROW,
    INDEX_LBUSER1,
)


def get_type(int_hdr) -> str:
    """TODO."""
    match int(int_hdr[INDEX_LBUSER1]):
        case 1:
            return "real"

        case 2:
            return "integer"

        case 3:
            return "logical"

        case _:
            # Fall back to real
            return "real"


def get_extra_data_length(int_hdr, word_size: int) -> int:
    """TODO."""
    LBEXT = int_hdr[INDEX_LBEXT]
    if LBEXT > 0:
        return int(LBEXT) * word_size

    return 0


def get_num_data_words(int_hdr, word_size: int) -> int:
    """TODO."""
    LBROW = int_hdr[INDEX_LBROW]
    LBNPT = int_hdr[INDEX_LBNPT]
    if int_hdr[INDEX_LBPACK] != 0 and LBROW > 0 and LBNPT > 0:
        return int(LBROW) * int(LBNPT)

    return int(int_hdr[INDEX_LBLREC]) - (
        get_extra_data_length(int_hdr, word_size) // word_size
    )


def get_type_and_num_words(int_hdr, word_size: int):
    """TODO."""
    return get_type(int_hdr), get_num_data_words(int_hdr, word_size)


def get_extra_data_offset_and_length(
    int_hdr, data_offset: int, disk_length: int, word_size: int
):
    """TODO."""
    extra_data_length = get_extra_data_length(int_hdr, word_size)
    if int_hdr[INDEX_LBPACK] != 0:
        extra_data_offset = data_offset + disk_length - extra_data_length
    else:
        extra_data_offset = data_offset + (
            get_num_data_words(int_hdr, word_size) * word_size
        )

    return extra_data_offset, extra_data_length


def get_ff_disk_length(int_hdr, word_size: int):
    """TODO."""
    LBPACK = int(int_hdr[INDEX_LBPACK])
    LBNREC = int_hdr[INDEX_LBNREC]
    if LBPACK != 0 and LBNREC != 0:
        return int(LBNREC) * word_size

    if LBPACK % 10 == 2:
        return get_num_data_words(int_hdr, word_size) * 4

    return int(int_hdr[INDEX_LBLREC]) * word_size
