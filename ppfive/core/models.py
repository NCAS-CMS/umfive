from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FileTypeInfo:
    fmt: str
    byte_ordering: str
    word_size: int


@dataclass
class RecordInfo:
    int_hdr: np.ndarray
    real_hdr: np.ndarray
    header_offset: int
    data_offset: int
    disk_length: int
    extra_data: None


@dataclass(frozen=True)
class StoreInfo:
    chunk_offset: tuple[int, ...]
    filter_mask: int
    byte_offset: int
    size: int
