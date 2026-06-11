from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class FileTypeInfo:
    """File-type information.

    **Initialisation**

    :Parameters:

        fmt: `str`
            The file format, either ``'PP'`` or ``'FF'``.

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

        word_size: `int`
            The word size (``4`` or ``8``).

    """

    fmt: str
    byte_order: str
    word_size: int


@dataclass
class RecordInfo:
    """A lookup header record with associated information.

    **Initialisation**

    :Parameters:

        int_hdr: `numpy.ndarray`
            The 1-d array of the integer lookup header.

        real_hdr: `numpy.ndarray`
            The 1-d array of the real lookup header.

        header_offset: `int`
            The byte address of the start of the integer header in the
            file.

        data_offset: `int`
            The byte address of the start of the data in the file.

        disk_length: `int`
            The length in bytes of the data, including any extra data.

        word_size: `int`
            The word size (``4`` or ``8``).

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

        extra_data: `dict`
            Any parsed extra data. If there is no extra data then the
            dictionary will be empty.

    """

    int_hdr: np.ndarray
    real_hdr: np.ndarray
    header_offset: int
    data_offset: int
    disk_length: int
    word_size: int
    byte_order: int
    extra_data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StoreInfo:
    """Store of chunk information.

    **Initialisation**

    :Parameters:

        chunk_offset: `tuple` of `int`
            The chunk index (e.g. ``(1, 4, 0, 0)``).

        filter_mask: `int`
            The compression filter indicator. A value of ``0`` means
            every filter defined in the dataset's pipeline was
            successfully applied to this chunk.

        byte_offset: `int`
            The byte address of the start of the data in the file.

        size: `int`
            The size in bytes of the data, including any extra data.

    """

    chunk_offset: tuple[int, ...]
    filter_mask: int
    byte_offset: int
    size: int
