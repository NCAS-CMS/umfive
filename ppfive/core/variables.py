from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import datetime
from typing import Any

import numpy as np

from ppfive.io.fsspec_reader import FsspecReader
from ppfive.io.local import LocalPosixReader

from .constants import (
    INDEX_BDX,
    INDEX_BDY,
    INDEX_BGOR,
    INDEX_BHLEV,
    INDEX_BLEV,
    INDEX_BPLAT,
    INDEX_BPLON,
    INDEX_BZX,
    INDEX_BZY,
    INDEX_LBCODE,
    INDEX_LBDAT,
    INDEX_LBDATD,
    INDEX_LBDAY,
    INDEX_LBDAYD,
    INDEX_LBFT,
    INDEX_LBFC,
    INDEX_LBHEM,
    INDEX_LBHR,
    INDEX_LBHRD,
    INDEX_LBREL,
    INDEX_LBLEV,
    INDEX_LBMIN,
    INDEX_LBMIND,
    INDEX_LBMON,
    INDEX_LBMOND,
    INDEX_LBNPT,
    INDEX_LBPACK,
    INDEX_LBPROC,
    INDEX_LBROW,
    INDEX_LBTIM,
    INDEX_LBSRCE,
    INDEX_LBUSER4,
    INDEX_LBUSER5,
    INDEX_LBUSER7,
    INDEX_LBVC,
    INDEX_LBYR,
    INDEX_LBYRD,
    INT_MISSING_DATA,
)
from .data import (
    decode_record_array_from_raw,
    get_record_packed_nbytes,
    read_record_array,
)
from .interpret import get_type
from .models import RecordInfo


def _float_key(val: float) -> float:
    return round(float(val), 9)


def _between_var_key(rec: RecordInfo) -> tuple[Any, ...]:
    ih = rec.int_hdr
    rh = rec.real_hdr
    return (
        int(ih[INDEX_LBUSER4]),
        int(ih[INDEX_LBUSER7]),
        int(ih[INDEX_LBCODE]),
        int(ih[INDEX_LBVC]),
        int(ih[INDEX_LBTIM]),
        int(ih[INDEX_LBPROC]),
        _float_key(rh[INDEX_BPLAT]),
        _float_key(rh[INDEX_BPLON]),
        int(ih[INDEX_LBHEM]),
        int(ih[INDEX_LBROW]),
        int(ih[INDEX_LBNPT]),
        _float_key(rh[INDEX_BGOR]),
        _float_key(rh[INDEX_BZY]),
        _float_key(rh[INDEX_BDY]),
        _float_key(rh[INDEX_BZX]),
        _float_key(rh[INDEX_BDX]),
    )


def _within_var_key(rec: RecordInfo) -> tuple[Any, ...]:
    ih = rec.int_hdr
    rh = rec.real_hdr
    lblev = int(ih[INDEX_LBLEV])
    lblev_rank = -1 if lblev == 9999 else lblev
    return (
        int(ih[INDEX_LBFT]),
        int(ih[INDEX_LBYR]),
        int(ih[INDEX_LBMON]),
        int(ih[INDEX_LBDAT]),
        int(ih[INDEX_LBDAY]),
        int(ih[INDEX_LBHR]),
        int(ih[INDEX_LBMIN]),
        int(ih[INDEX_LBYRD]),
        int(ih[INDEX_LBMOND]),
        int(ih[INDEX_LBDATD]),
        int(ih[INDEX_LBDAYD]),
        int(ih[INDEX_LBHRD]),
        int(ih[INDEX_LBMIND]),
        lblev_rank,
        _float_key(rh[INDEX_BLEV]),
        _float_key(rh[INDEX_BHLEV]),
    )


def _record_is_skippable(rec: RecordInfo) -> bool:
    ih = rec.int_hdr

    # Mirrors key skip logic in process_vars.c
    if int(ih[INDEX_LBNPT]) == INT_MISSING_DATA:
        return True
    if int(ih[INDEX_LBROW]) == INT_MISSING_DATA:
        return True

    compression = (int(ih[INDEX_LBPACK]) // 10) % 10
    if compression == 1:
        return True

    return False


def _dtype_name(first: RecordInfo, word_size: int) -> str:
    kind = get_type(first.int_hdr)
    if kind == "integer":
        return "int32" if word_size == 4 else "int64"
    
    return "float32" if word_size == 4 else "float64"


def _z_key(rec: RecordInfo) -> tuple[Any, ...]:
    ih = rec.int_hdr
    pseudo = int(ih[INDEX_LBUSER5])
    if pseudo in (0, INT_MISSING_DATA):
        pseudo = None

    within = _within_var_key(rec)
    return (pseudo, within[13], within[14], within[15])


def _t_key(rec: RecordInfo) -> tuple[Any, ...]:
    return _within_var_key(rec)[:13]


def _split_on_duplicate_tz_pairs(recs: list[RecordInfo]) -> list[list[RecordInfo]]:
    """Split a grouped variable when (t,z) coordinate pairs are duplicated.

    This mirrors the key behavior of the legacy disambiguation index in
    process_vars.c for non-regular z/t record layouts.
    """
    seen: dict[tuple[Any, Any], int] = defaultdict(int)
    buckets: dict[int, list[RecordInfo]] = defaultdict(list)

    for rec in recs:
        pair = (_t_key(rec), _z_key(rec))
        bucket = seen[pair]
        seen[pair] += 1
        buckets[bucket].append(rec)

    if len(buckets) <= 1:
        return [recs]

    return [buckets[index] for index in sorted(buckets)]


def build_variable_index(
    records: list[RecordInfo],
    reader,
    word_size: int,
    byte_ordering: str,
    parallel_config: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    if parallel_config is None:
        parallel_config = {"thread_count": 0, "cat_range_allowed": True}

    filtered = [r for r in records if not _record_is_skippable(r)]
    ordered = sorted(filtered, key=lambda r: (_between_var_key(r), _within_var_key(r)))

    grouped: dict[tuple[Any, ...], list[RecordInfo]] = defaultdict(list)
    for rec in ordered:
        grouped[_between_var_key(rec)].append(rec)

    variable_index: dict[str, dict[str, Any]] = {}

    # Assign an integer code to each data variable. This is used as
    # the key in 'variable_index'.
    int_code = 0
    
    for _, recs in grouped.items():
        for recs_split in _split_on_duplicate_tz_pairs(recs):
            first = recs_split[0]

            z_keys_set = {_z_key(r) for r in recs_split}
            has_pseudo = any(zk[0] is not None for zk in z_keys_set)
            depth = first.int_hdr[INDEX_LBVC] == 2
            # Don't reverse pseudolevels and depth levels
            z_levels = sorted(z_keys_set, reverse=not has_pseudo and not depth)
            t_steps = sorted({_t_key(r) for r in recs_split})
            z_index = {k: i for i, k in enumerate(z_levels)}
            t_index = {k: i for i, k in enumerate(t_steps)}

            ny = int(first.int_hdr[INDEX_LBROW])
            nx = int(first.int_hdr[INDEX_LBNPT])
            nz = len(z_levels)
            nt = len(t_steps)
            dtype = np.dtype(_dtype_name(first, word_size))
            packing_modes = sorted({int(rec.int_hdr[INDEX_LBPACK]) % 10 for rec in recs_split})
            compression_modes = sorted({(int(rec.int_hdr[INDEX_LBPACK]) // 10) % 10 for rec in recs_split})
            z_first = has_pseudo and nt > 1 and nz > 1
            chunk_records = []

            for rec in recs_split:
                ti = t_index[_t_key(rec)]
                zi = z_index[_z_key(rec)]
                chunk_coords = (zi, ti, 0, 0) if z_first else (ti, zi, 0, 0)
                chunk_records.append(
                    {
                        "record": rec,
                        "chunk_coords": chunk_coords,
                    }
                )

            def _make_loader(group_recs, _nt, _nz, _ny, _nx, _dtype,
                             _t_index, _z_index, _z_first):
                def _load():
                    if _z_first:                        
                        out_shape = (_nz, _nt, _ny, _nx)
                    else:
                        out_shape = (_nt, _nz, _ny, _nx)
                        
                    out = np.empty(out_shape, dtype=_dtype)
                    out.fill(np.nan if _dtype.kind == "f" else 0)

                    thread_count = int(parallel_config.get("thread_count", 0) or 0)
                    cat_range_allowed = bool(parallel_config.get("cat_range_allowed", True))

                    # Strategy A: fsspec bulk range reads for unpacked records.
                    if thread_count != 0 and cat_range_allowed and isinstance(reader, FsspecReader):
                        fh = getattr(reader, "_fh", None)
                        actual_fh = getattr(fh, "fh", fh)
                        if actual_fh is not None and hasattr(actual_fh, "fs") and hasattr(actual_fh.fs, "cat_ranges"):
                            path = actual_fh.path
                            starts = [rec.data_offset for rec in group_recs]
                            stops = [rec.data_offset + get_record_packed_nbytes(rec, word_size) for rec in group_recs]
                            buffers = actual_fh.fs.cat_ranges([path] * len(group_recs), starts, stops)

                            items = list(zip(group_recs, buffers))

                            def _decode_one(item):
                                rec, raw = item
                                ti = _t_index[_t_key(rec)]
                                zi = _z_index[_z_key(rec)]
                                values = decode_record_array_from_raw(raw, rec, word_size, byte_ordering)
                                return ti, zi, values

                            if thread_count > 1:
                                with ThreadPoolExecutor(max_workers=thread_count) as executor:
                                    decoded = executor.map(_decode_one, items)
                                    for ti, zi, values in decoded:
                                        if _z_first:
                                            out[zi, ti, :, :] = values.reshape((_ny, _nx))
                                        else:
                                            out[ti, zi, :, :] = values.reshape((_ny, _nx))
                            else:
                                for ti, zi, values in map(_decode_one, items):
                                    if _z_first:
                                        out[zi, ti, :, :] = values.reshape((_ny, _nx))
                                    else:
                                        out[ti, zi, :, :] = values.reshape((_ny, _nx))

                            return out

                    # Strategy B: local threaded reads using os.pread-backed reader.
                    if thread_count != 0 and isinstance(reader, LocalPosixReader):
                        def _read_one(rec):
                            ti = _t_index[_t_key(rec)]
                            zi = _z_index[_z_key(rec)]
                            values = read_record_array(reader, rec, word_size, byte_ordering)
                            return ti, zi, values

                        with ThreadPoolExecutor(max_workers=thread_count) as executor:
                            for ti, zi, values in executor.map(_read_one, group_recs):
                                if _z_first:
                                    out[zi, ti, :, :] = values.reshape((_ny, _nx))
                                else:
                                    out[ti, zi, :, :] = values.reshape((_ny, _nx))
                                    
                        return out

                    # Strategy C: serial fallback.
                    for rec in group_recs:
                        ti = _t_index[_t_key(rec)]
                        zi = _z_index[_z_key(rec)]
                        values = read_record_array(reader, rec, word_size, byte_ordering)
                        if _z_first:
                            out[zi, ti, :, :] = values.reshape((_ny, _nx))
                        else:
                            out[ti, zi, :, :] = values.reshape((_ny, _nx))
                            
                    return out

                return _load

            variable_index[int_code] = {
                "attrs": {},
                "shape": (nz, nt, ny, nx) if z_first else (nt, nz, ny, nx),
                "dtype": _dtype_name(first, word_size),
                "chunk_shape": (1, 1, ny, nx),
                "records": recs_split,
                "chunk_records": chunk_records,
                "data_loader": _make_loader(
                    recs_split,
                    nt,
                    nz,
                    ny,
                    nx,
                    dtype,
                    t_index,
                    z_index,
                    z_first,
                ),
                "z_first": z_first
            }

            int_code += 1

    return variable_index
