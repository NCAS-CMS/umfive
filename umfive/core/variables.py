from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np

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
    INDEX_LBLREC,
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
from ..io import ByteReader, LocalPosixReader
from .data import (
    decode_record_array_from_raw,
    get_record_packed_nbytes,
    read_record_array,
)
from .interpret import get_type


def _float_key(val):
    """Convert a value to a rounded `float`.

    :Parameters:

        val:
            The value to convert.

    :Returns:

        `float`

    """
    return round(float(val), 9)


def _between_var_key(rec):
    """Key to discern records that belong in a group.

    :Parameters:

        rec: `RecordInfo`
            The record from which to derive the key.

    :Returns:

        `tuple`
            A tuple of values derived from the lookup header.

    """
    ih = rec.int_hdr
    rh = rec.real_hdr

    # Only set LBLREC to a meaningful value for compressed records (in
    # other cases LBLREC may reasonably be different for records that
    # are in the same group)
    if int(ih[INDEX_LBPACK]) in (120, 220):
        # Compressed
        LBLREC = int(ih[INDEX_LBLREC])
    else:
        # Not compressed
        LBLREC = -1

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
        LBLREC,
        _float_key(rh[INDEX_BGOR]),
        _float_key(rh[INDEX_BZY]),
        _float_key(rh[INDEX_BDY]),
        _float_key(rh[INDEX_BZX]),
        _float_key(rh[INDEX_BDX]),
    )


def _within_var_key(rec):
    """Key to discern records within a group.

    The group is defined by `_between_var_key`.

    :Parameters:

        rec: `RecordInfo`
            The record from which to derive the key.

    :Returns:

        `tuple`
            A tuple of values derived from the lookup header.

    """
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


def _record_is_skippable(rec):
    """Whether or not the record should be skipped.

    :Parameters:

        rec: `RecordInfo`
            The record.

    :Returns:

        `bool`
            `True` is the record is skippable, otherwise `False`.

    """
    ih = rec.int_hdr
    if int(ih[INDEX_LBNPT]) == INT_MISSING_DATA:
        return True

    if int(ih[INDEX_LBROW]) == INT_MISSING_DATA:
        return True

    compression_N2 = (int(ih[INDEX_LBPACK]) // 10) % 10
    if compression_N2 == 1:
        return True

    return False


def _dtype_name(rec):
    """The data type of the record data array.

    :Parameters:

        rec: `RecordInfo`
            The record.

    :Returns:

        `str`
            The data type.

    """
    word_size = rec.word_size

    kind = get_type(rec.int_hdr)
    if kind == "integer":
        return "int32" if word_size == 4 else "int64"

    return "float32" if word_size == 4 else "float64"


def _z_key(rec):
    """Return a key for Z information.

    :Parameters:

        rec: `RecordInfo`
            The record.

    :Returns:

        `tuple`

    """
    ih = rec.int_hdr
    pseudo = int(ih[INDEX_LBUSER5])
    if pseudo in (0, INT_MISSING_DATA):
        pseudo = None

    within = _within_var_key(rec)
    return (pseudo, within[13], within[14], within[15])


def _t_key(rec):
    """Return a key for T information.

    :Parameters:

        rec: `RecordInfo`
            The record.

    :Returns:

        `tuple`

    """
    return _within_var_key(rec)[:13]


def _split_on_duplicate_tz_pairs_and_extra_data(recs):
    """Split a grouped variable on duplicate (t,z) coordinate pairs.

    Split a grouped variable when (t,z) coordinate pairs are duplicated.

    This mirrors the key behaviour of the legacy disambiguation index in
    process_vars.c for non-regular z/t record layouts.

    Also split when extra data differs, after splitting duplicate
    (t,z) coordinate pairs.

    :Parameters:

        recs: sequence of `RecordInfo`
            The records.

    :Returns:

        `list`
            Each element is a `list` of `RecordInfo`

    """
    seen = defaultdict(int)
    buckets = defaultdict(list)

    for rec in recs:
        pair = (_t_key(rec), _z_key(rec))
        bucket = seen[pair]
        seen[pair] += 1
        buckets[bucket].append(rec)

    if len(buckets) <= 1:
        return [recs]

    recs_tz = [buckets[index] for index in sorted(buckets)]

    return _split_groups_by_extra_data(recs_tz)


def _split_groups_by_extra_data(recs_tz):
    """Split groups by extra data.

    :Parameters:

        recs_tz: `list` of `list`
            Each of the groups derived from splitting on duplicate
            (t,z) coordinate pairs.

    :Returns:

        `dict`
            The new groups taking extra data into account.

    """
    out = []
    for recs in recs_tz:
        split = False
        rec0 = recs[0]
        for rec1 in recs[1:]:
            if not _equal_extra_data(rec0, rec1):
                split = True
                break

        if split:
            out.extend([rec] for rec in recs)
        else:
            out.append(recs)

    return out


def _equal_extra_data(rec0, rec1):
    """Whether the extra data of two records are equal.

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
    extra1 = rec1.extra_data

    if not extra0:
        if not extra1:
            return True

        return False

    if not extra1:
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

        else:
            raise ValueError(
                "Invalid data type for extra data key "
                f"{key!r}: {value0.dtype!r}"
            )

    return True


def can_have_multiple_levels(rec):
    """Evaluates whether a data variable allows Z > 1.

    :Parameters:

        rec: `RecordInfo`
            The first loookup header for the data variable.

    :Returns:

        `bool`
            `True` if Z may be > 1, otherwise `False`.

    """
    lblev = rec.int_hdr[INDEX_LBLEV]
    lbvc = rec.int_hdr[INDEX_LBVC]
    lbuser5 = rec.int_hdr[INDEX_LBUSER5]

    # Pseudo-level check this FIRST (e.g. surface tiles, radiation
    # bands, plant functional types) UMDP F3: LBUSER5 > 0 indicates
    # pseudo-level index (1, 2, 3...)
    if lbuser5 > 0:
        return True

    # Multi-level field packed into a single header (e.g. LBCs)
    if lblev == 7777:
        return True

    # Surface and special single-level coordinates (126 <= LBVC <= 139
    # or LBVC == 0) 0: No vertical coord, 128: MSL, 129: Surface, 130:
    # Tropopause, 131: Max wind, 133: TOA without pseudo-levels
    # (LBUSER5 <= 0), ALL surface/special levels are strictly 2-d (Z =
    # 1).
    if (126 <= lbvc <= 139) or (lbvc == 0):
        return False

    # Explicit single-level non-surface diagnostic flag
    if lblev == 8888:
        return False

    # Continuous 3-d/multi-level vertical coordinate types
    # (atmosphere, ocean, soil) 1: height, 2: depth, 3: geopotential
    # height, 4: geometric height, 6: deep soil levels, 7: theta
    # surfaces, 8: pressure, 9: hybrid pressure, 10: sigma, 65: hybrid
    # height.
    multilevel_lbvc_codes = {1, 2, 3, 4, 6, 7, 8, 9, 10, 65}
    if lbvc in multilevel_lbvc_codes:
        return True

    # Default fallback
    return False


def build_data_variable_index(records, reader, parallelism):
    """Create a dictionary of data variable descriptions.

    :Parameters:

        records: sequence of `RecordInfo`
            All records from a file.

        reader: `ByteReader`
            The file reader.

        parallelism: `dict`
            A dictionary of read-parallelism configuration
            options. These are passed to the data-loader function
            (`load`) at data-read time.

    :Returns:

        `list` of `dict`
            A dictionary describing each data variable. Each
            dictionary contains all of the information needed to
            create a `DataVariable` instance and its associated
            `DimensionScale` and `Variable` instances.

    """
    if parallelism is None:
        parallelism = {}

    filtered = [r for r in records if not _record_is_skippable(r)]
    ordered = sorted(
        filtered, key=lambda r: (_between_var_key(r), _within_var_key(r))
    )

    grouped = defaultdict(list)
    for rec in ordered:
        grouped[_between_var_key(rec)].append(rec)

    variable_index = []

    # Assign a unique integer code to each data variable. This is used
    # as the key in the 'variable_index' dictionary.
    int_code = 0

    for recs in grouped.values():
        for recs_split in _split_on_duplicate_tz_pairs_and_extra_data(recs):
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

            z_levels = sorted(z_keys_set, reverse=bool(reverse))

            t_steps = sorted({_t_key(r) for r in recs_split})
            z_index = {k: i for i, k in enumerate(z_levels)}
            t_index = {k: i for i, k in enumerate(t_steps)}

            ny = int(first.int_hdr[INDEX_LBROW])
            nx = int(first.int_hdr[INDEX_LBNPT])
            nz = len(z_levels)
            nt = len(t_steps)

            is_single_level_surface = not can_have_multiple_levels(first)
            has_z_axis = not is_single_level_surface

            dtype = np.dtype(_dtype_name(first))

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

                rec.chunk_coords = chunk_coords
                chunk_records.append(rec)

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
                def _load(thread_count=0, cat_range_allowed=True, mask=None):
                    LBPACK = group_recs[0].int_hdr[INDEX_LBPACK]
                    if mask is not None:
                        # A mask has been provided, so we assume that
                        # the field is run length encoded.
                        if LBPACK not in (120, 220):
                            raise ValueError(
                                "Field is not run length encoded "
                                "f(LBPACK={LBPACK}) but a land/sea mask has "
                                "been provided. "
                                f"Lookup header:\n{group_recs[0]}"
                            )

                        # Reset (_ny, _nx) from (0, 0) to the shape of
                        # the mask
                        _ny, _nx = mask.shape[-2:]
                    else:
                        # No mask has been provided, implying that the
                        # field is not run length encoded.
                        mask = None
                        if LBPACK in (120, 220):
                            raise ValueError(
                                "Can't get run length encoded data "
                                f"(LBPACK={LBPACK}) when there is no suitable "
                                "land/sea mask (STASH code 30) in the "
                                f"dataset. Lookup header:\n{group_recs[0]}"
                            )

                    out_shape = (_nt, _nz, _ny, _nx)

                    out = np.empty(out_shape, dtype=_dtype)
                    out.fill(np.nan if _dtype.kind == "f" else 0)

                    # Strategy A: fsspec bulk range reads for unpacked
                    #             records.
                    if (
                        thread_count > 0
                        and cat_range_allowed
                        and isinstance(reader, ByteReader)
                    ):
                        fs = getattr(reader, "fs", None)
                        if hasattr(fs, "cat_ranges"):
                            path = reader.path
                            starts = [rec.data_offset for rec in group_recs]
                            stops = [
                                rec.data_offset + get_record_packed_nbytes(rec)
                                for rec in group_recs
                            ]
                            buffers = fs.cat_ranges(
                                [path] * len(group_recs), starts, stops
                            )

                            items = list(zip(group_recs, buffers))

                            def _decode_one(item):
                                rec, raw = item
                                ti = _t_index[_t_key(rec)]
                                zi = _z_index[_z_key(rec)]
                                values = decode_record_array_from_raw(
                                    raw, rec, mask=mask
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
                            values = read_record_array(reader, rec, mask=mask)
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
                        values = read_record_array(reader, rec, mask=mask)
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
                    "dtype": _dtype_name(first),
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
