from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

from ppfive.io.fsspec_reader import FsspecReader
from ppfive.io.local import LocalPosixReader

from ..constants import (
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
    INDEX_LBHEM,
    INDEX_LBHR,
    INDEX_LBHRD,
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


def _float_key(val) -> float:
    """TODO."""
    return round(float(val), 9)


def _between_var_key(rec: RecordInfo) -> tuple:
    """TODO."""
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


def _within_var_key(rec: RecordInfo) -> tuple:
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
    """TODO."""
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
    """TODO."""
    kind = get_type(first.int_hdr)
    if kind == "integer":
        return "int32" if word_size == 4 else "int64"

    return "float32" if word_size == 4 else "float64"


def _z_key(rec: RecordInfo) -> tuple:
    """TODO."""
    ih = rec.int_hdr
    pseudo = int(ih[INDEX_LBUSER5])
    if pseudo in (0, INT_MISSING_DATA):
        pseudo = None

    within = _within_var_key(rec)
    return (pseudo, within[13], within[14], within[15])


def _t_key(rec: RecordInfo) -> tuple:
    """TODO."""
    return _within_var_key(rec)[:13]


def _split_on_duplicate_tz_pairs(
    recs: list[RecordInfo],
) -> list[list[RecordInfo]]:
    """Split a grouped variable on duplicate (t,z) coordinate pairs.

    Split a grouped variable when (t,z) coordinate pairs are duplicated.

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


def build_data_variable_index(
    records: list[RecordInfo],
    reader,
    word_size: int,
    byte_ordering: str,
    parallelism: dict[str, Any] | None = None,
) -> dict[int, dict[str, Any]]:
    """TODO."""
    if parallelism is None:
        parallelism = {}

    filtered = [r for r in records if not _record_is_skippable(r)]
    ordered = sorted(
        filtered, key=lambda r: (_between_var_key(r), _within_var_key(r))
    )

    grouped = defaultdict(list)
    for rec in ordered:
        grouped[_between_var_key(rec)].append(rec)

    grouped = split_groups_by_extra_data(grouped)

    variable_index = []

    # Assign a unique integer code to each data variable. This is used
    # as the key in the 'variable_index' dictionary.
    int_code = 0

    for _, recs in grouped.items():
        for recs_split in _split_on_duplicate_tz_pairs(recs):
            first = recs_split[0]

            # Relevant LBVC codes
            # -------------------
            #   0  Unspecified
            #   8  Pressure
            # 126  Max C.A.T. level
            # 127  Sea bed level
            # 128  Mean sea level
            # 129  Surface
            # 130  Tropopause level
            # 131  Maximum wind level
            # 132  Freezing level
            # 133  Top of atmosphere
            # 134  -20 deg.C level
            # 135  Upper level (height)
            # 136  Lower level (height)
            # 137  Upper level (pressure)
            # 138  Lower level (pressure)
            # 139  Wet bulb freezing level height (asl) m
            LBVC = first.int_hdr[INDEX_LBVC]

            z_keys_set = {_z_key(r) for r in recs_split}

            # Reverse air_pressure axis
            reverse = LBVC == 8

            z_levels = sorted(z_keys_set, reverse=reverse)

            t_steps = sorted({_t_key(r) for r in recs_split})
            z_index = {k: i for i, k in enumerate(z_levels)}
            t_index = {k: i for i, k in enumerate(t_steps)}

            ny = int(first.int_hdr[INDEX_LBROW])
            nx = int(first.int_hdr[INDEX_LBNPT])
            nz = len(z_levels)
            nt = len(t_steps)

            is_single_level_surface = (
                nz == 1
                and 126 <= LBVC <= 139
                or (
                    LBVC == 0
                    and first.int_hdr[INDEX_LBLEV] in (8888, 9999)
                    and first.int_hdr[INDEX_LBUSER5] == 0
                )
            )
            has_z_axis = not is_single_level_surface

            dtype = np.dtype(_dtype_name(first, word_size))

            # # Digit N1 of LBPACK = N5N4N3N2N1
            # packing_modes = sorted(
            #      {int(rec.int_hdr[INDEX_LBPACK]) % 10 for rec in recs_split}
            # )
            #
            # # Digit N2 of LBPACK = N5N4N3N2N1
            # compression_modes = sorted(
            #     {
            #         (int(rec.int_hdr[INDEX_LBPACK]) // 10) % 10
            #         for rec in recs_split
            #     }
            # )

            chunk_records = []
            for rec in recs_split:
                ti = t_index[_t_key(rec)]
                zi = z_index[_z_key(rec)]

                if has_z_axis:
                    chunk_coords = (ti, zi, 0, 0)
                else:
                    chunk_coords = (ti, 0, 0)

                chunk_records.append(
                    {"record": rec, "chunk_coords": chunk_coords}
                )

            def _make_loader(
                group_recs,
                _nt,
                _nz,
                _ny,
                _nx,
                _dtype,
                _t_index,
                _z_index,
                _has_z_axis,
            ):
                def _load(thread_count=0, cat_range_allowed=True):
                    out_shape = (_nt, _nz, _ny, _nx)

                    out = np.empty(out_shape, dtype=_dtype)
                    out.fill(np.nan if _dtype.kind == "f" else 0)

                    # Strategy A: fsspec bulk range reads for unpacked
                    #             records.
                    if (
                        #                        thread_count != 0
                        cat_range_allowed
                        and isinstance(reader, FsspecReader)
                    ):
                        fh = getattr(reader, "_fh", None)
                        actual_fh = getattr(fh, "fh", fh)
                        if (
                            actual_fh is not None
                            and hasattr(actual_fh, "fs")
                            and hasattr(actual_fh.fs, "cat_ranges")
                        ):
                            path = actual_fh.path
                            starts = [rec.data_offset for rec in group_recs]
                            stops = [
                                rec.data_offset
                                + get_record_packed_nbytes(rec, word_size)
                                for rec in group_recs
                            ]
                            buffers = actual_fh.fs.cat_ranges(
                                [path] * len(group_recs), starts, stops
                            )

                            items = list(zip(group_recs, buffers))

                            def _decode_one(item):
                                rec, raw = item
                                ti = _t_index[_t_key(rec)]
                                zi = _z_index[_z_key(rec)]
                                values = decode_record_array_from_raw(
                                    raw, rec, word_size, byte_ordering
                                )
                                return ti, zi, values

                            if thread_count > 1:
                                with ThreadPoolExecutor(
                                    max_workers=thread_count
                                ) as executor:
                                    decoded = executor.map(_decode_one, items)
                                    for ti, zi, values in decoded:
                                        out[ti, zi, :, :] = values.reshape(
                                            (_ny, _nx)
                                        )
                            else:
                                for ti, zi, values in map(_decode_one, items):
                                    out[ti, zi, :, :] = values.reshape(
                                        (_ny, _nx)
                                    )

                            if not _has_z_axis:
                                # Remove a non-existent Z axis
                                out = np.squeeze(out, axis=1)

                            return out

                    # Strategy B: local threaded reads using
                    #             os.pread-backed reader.
                    if thread_count > 0 and isinstance(
                        reader, LocalPosixReader
                    ):

                        def _read_one(rec):
                            ti = _t_index[_t_key(rec)]
                            zi = _z_index[_z_key(rec)]
                            values = read_record_array(
                                reader, rec, word_size, byte_ordering
                            )
                            return ti, zi, values

                        with ThreadPoolExecutor(
                            max_workers=thread_count
                        ) as executor:
                            for ti, zi, values in executor.map(
                                _read_one, group_recs
                            ):
                                out[ti, zi, :, :] = values.reshape((_ny, _nx))

                        if not _has_z_axis:
                            # Remove a non-existent Z axis
                            out = np.squeeze(out, axis=1)

                        return out

                    # Strategy C: serial fallback.
                    for rec in group_recs:
                        ti = _t_index[_t_key(rec)]
                        zi = _z_index[_z_key(rec)]
                        values = read_record_array(
                            reader, rec, word_size, byte_ordering
                        )
                        out[ti, zi, :, :] = values.reshape((_ny, _nx))

                    if not _has_z_axis:
                        # Remove a non-existent Z axis
                        out = np.squeeze(out, axis=1)

                    return out

                return _load

            if has_z_axis:
                axis_order = "tzyx"
                shape = (nt, nz, ny, nx)
                chunk_shape = (1, 1, ny, nx)
            else:
                axis_order = "tyx"
                shape = (nt, ny, nx)
                chunk_shape = (1, ny, nx)

            variable_index.append(
                {
                    "attrs": {},
                    "shape": shape,
                    "dtype": _dtype_name(first, word_size),
                    "chunk_shape": chunk_shape,
                    "records": recs_split,
                    "chunk_records": chunk_records,
                    "axis_order": axis_order,
                    "data_loader": _make_loader(
                        recs_split,
                        nt,
                        nz,
                        ny,
                        nx,
                        dtype,
                        t_index,
                        z_index,
                        has_z_axis,
                    ),
                    "data_loader_options": parallelism.copy(),
                }
            )

            int_code += 1

    return variable_index


def split_groups_by_extra_data(grouped):
    """Split groups by extra data.

    :Parameters:

        groups: `dict`
            The groups derived with ignoring extra data.

    :Returns:

        `dict`
            The new groups taking extra data into account.

    """
    new_grouped = {}

    for key, recs in grouped.items():
        split = False

        rec0 = recs[0]
        for rec1 in recs[1:]:
            if not equal_extra_data(rec0, rec1):
                split = True
                break

        if split:
            # This group doesn't form a complete nz x nt matrix,
            # so split it up into 1 x 1 groups.
            for i, rec in enumerate(recs):
                new_grouped[key + (f"extra_data_{i}")] = [rec]
        else:
            new_grouped[key] = recs

    return new_grouped


def equal_extra_data(rec0, rec1):
    """Whether two sets of record extra data are equal.

    :Parameters:

        rec0: `RecordInfo`
            The first record.

        rec1: `RecordInfo`
            The second record.

    :Returns:

        `bool`
            Whether or not the records' extra data are equal.

    """
    extra0 = rec0.extra_data
    extra1 = rec0.extra_data

    if extra0 is None:
        if extra1 is None:
            return True

        return False

    if extra1 is None:
        return False

    if sorted(extra0.keys()) != sorted(extra1.keys()):
        return False

    for key, value0 in extra0.items():
        value1 = extra1[key]

        kind = value0.dtype.kind
        if kind == "f":
            itemsize = value0.dtype.itemsize
            if itemsize == 4:
                rtol = 1e-5
            elif itemsize == 8:
                rtol = 1e-13

            if not np.allclose(value0, value1, atol=0, rtol=rtol):
                return False

        elif kind in "iSUT":
            if not np.array_equal(value0, value1):
                return False

    return True
