from __future__ import annotations

from typing import Any

import numpy as np

from ppfive.io.base import ByteReader

from .data import read_record_array
from .models import RecordInfo


def materialize_reference_dict(
    reader: ByteReader, reference: dict[str, Any]
) -> np.ndarray:
    """Materialize an array from a JSON-serializable chunk reference mapping."""

    shape = tuple(reference["shape"])
    chunk_shape = tuple(reference["chunk_shape"])
    dtype = np.dtype(reference["dtype"])
    word_size = int(reference["word_size"])
    byte_ordering = reference["byte_ordering"]

    out = np.empty(shape, dtype=dtype)
    if dtype.kind == "f":
        out.fill(np.nan)
    else:
        out.fill(0)

    for ref in reference["refs"].values():
        rec = RecordInfo(
            int_hdr=np.array(ref["int_hdr"]),
            real_hdr=np.array(ref["real_hdr"]),
            header_offset=int(ref["header_offset"]),
            data_offset=int(ref["data_offset"]),
            disk_length=int(ref["disk_length"]),
        )
        values = read_record_array(reader, rec, word_size, byte_ordering)

        chunk_coords = tuple(ref["chunk_coords"])
        selection = []
        target_shape = []
        for coord, csize, full in zip(chunk_coords, chunk_shape, shape):
            start = coord * csize
            stop = min(start + csize, full)
            selection.append(slice(start, stop, 1))
            target_shape.append(stop - start)

        out[tuple(selection)] = values.reshape(tuple(target_shape))

    return out
