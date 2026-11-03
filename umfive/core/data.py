import numpy as np

from ..constants import INDEX_BMDI, INDEX_LBLREC, INDEX_LBPACK
from ..wgdos import unpack_wgdos
from .header import endian_prefix
from .interpret import get_extra_data_length, get_num_data_words, get_type


def _dtype_for_record(rec):
    """The datatype of the data array.

    :Parameter:

        rec: `RecordInfo`
            The record for the data array.

    :Returns:

        `numpy.dtype`

    """
    word_size = rec.word_size
    data_type = get_type(rec.int_hdr)
    prefix = endian_prefix(rec.byte_order)
    if data_type == "integer":
        return np.dtype(f"{prefix}i{word_size}")

    return np.dtype(f"{prefix}f{word_size}")


def _unpack_cray32(raw, nwords, byte_order, word_size):
    """Unpack cray32 data.

    :Parameter:

        raw: `bytes`
            The raw bytes of the packed data.

        nwords: `int`
            The number of words in the unpacked data.

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

        word_size: `int`
            The word size (``4`` or ``8``).

    :Returns:

        `numpy.ndarray`

    """
    prefix = endian_prefix(byte_order)
    packed = np.frombuffer(
        raw[: nwords * 4], dtype=np.dtype(f"{prefix}f4"), count=nwords
    )
    if word_size == 4:
        return packed.astype(np.float32, copy=True)

    return packed.astype(np.float64, copy=True)


def _unpack_runlength_encoded(raw, nwords, byte_order, word_size, mdi):
    """Unpack runlength encoded data.

    :Parameters:

        raw: `bytes`
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
    prefix = endian_prefix(byte_order)
    packed_dtype = np.dtype(f"{prefix}f{word_size}")
    packed = np.frombuffer(raw, dtype=packed_dtype)
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


def get_record_packed_nbytes(rec):
    """Get the size of the data on disk, excluding any extra data.

    :Parameters:

        rec: `RecordInfo`
            The record for the data array.

    :Returns:

        `int`
            The packed data size in bytes.

    """
    extra_bytes = get_extra_data_length(rec.int_hdr, rec.word_size)
    packed_bytes = rec.disk_length - extra_bytes

    # For packed fields, LBNREC can include alignment padding while
    # LBLREC reflects the actual packed payload length.
    if int(rec.int_hdr[INDEX_LBPACK]) != 0:
        lblrec_bytes = (int(rec.int_hdr[INDEX_LBLREC]) * rec.word_size) - (
            extra_bytes
        )
        if lblrec_bytes > 0:
            packed_bytes = min(packed_bytes, lblrec_bytes)

    return max(0, packed_bytes)


def read_record_raw(reader, rec):
    """Read packed data into raw bytes, without unpacking it.

    :Parameters:

        reader: `ByteReader`
            The file reader.

        rec: `RecordInfo`
            The record for the data array.

    :Returns:

        `bytes`
            The raw bytes of the packed data.

    """
    packed_bytes = get_record_packed_nbytes(rec)
    raw = reader.read_at(rec.data_offset, packed_bytes)
    if len(raw) < packed_bytes:
        raise ValueError("Short read while loading raw record bytes")

    return raw


def decode_record_array_from_raw(raw, rec, mask=None):
    """Decode packed data.

    :Parameters:

        raw: `bytes`
            The raw bytes of the packed data.

        rec: `RecordInfo`
            The record for the data array.

        mask: `numpy.ndarray` or `None`, optional
            When set to a numpy array, it must contain the land-sea
            mask for the field that is required for decompressing run
            length encoded fields. It must have shape (LBROW, LBNPT)
            and contain Booleans such that True indicates a land grid
            cell and False indicates a sea grid cell. The default of
            `None` indicates that no land/sea mask required, or else
            one is required but it could not be found.

            .. versionadded:: 0.5.0

    :Returns:

        `nump.ndarray`
            The 1-d array of the decoded data.

    """
    word_size = rec.word_size
    byte_order = rec.byte_order
    lbpack = int(rec.int_hdr[INDEX_LBPACK])
    pack = lbpack % 10
    nwords = get_num_data_words(rec.int_hdr, word_size)

    if pack == 0:
        # The data is not packed (but might be compressed)
        if lbpack in (120, 220):
            # The data is compressed
            if mask is None:
                raise RuntimeError(
                    f"Cannot uncompress field with LBPACK={lbpack}: no "
                    "suitable land/sea mask found in dataset. "
                    f"Lookup header:\n{rec}"
                )

            dtype = _dtype_for_record(rec)
            compressed_data = np.frombuffer(raw, dtype=dtype)
            out = np.full(mask.shape, rec.real_hdr[INDEX_BMDI], dtype=dtype)

            if lbpack == 220:
                # Convert the mask to a Boolean array that is True for
                # sea grid cell cells (on my laptop this takes ~150
                # microseconds for an array of size 5000000)
                mask = ~mask

            out[mask] = compressed_data
            return out.ravel()

        # Still here? Then the data is neither packed nor compressed.
        need = nwords * word_size
        dtype = _dtype_for_record(rec)
        return np.frombuffer(raw[:need], dtype=dtype, count=nwords).copy()

    # Still here? Then the data is packed.
    if pack == 1:
        mdi = float(rec.real_hdr[INDEX_BMDI])
        return unpack_wgdos(raw, nwords, mdi, word_size)

    if pack == 2:
        return _unpack_cray32(raw, nwords, byte_order, word_size)

    if pack == 4:
        mdi = float(rec.real_hdr[INDEX_BMDI])
        return _unpack_runlength_encoded(
            raw, nwords, byte_order, word_size, mdi
        )

    if pack == 3:
        raise NotImplementedError("GRIB packed data is not supported")

    raise NotImplementedError(
        f"Packed data mode {pack} is not implemented yet"
    )


def read_record_array(reader, rec, mask=None):
    """Read a data array into a `numpy` array.

    :Parameters:

        reader: `ByteReader`
            The file reader.

        rec: `RecordInfo`
            The record for the data array.

        mask: `numpy.ndarray` or `None`, optional
            When set to a numpy array, it must contain the land-sea
            mask for the field that is required for decompressing run
            length encoded fields. It must have shape (LBROW, LBNPT)
            and contain Booleans such that True indicates a land grid
            cell and False indicates a sea grid cell. The default of
            `None` indicates that no land/sea mask required, or else
            one is required but it could not be found.

            .. versionadded:: 0.5.0

    :Returns:

        `nump.ndarray`
            The 1-d array of the decoded data.

    """
    raw = read_record_raw(reader, rec)
    return decode_record_array_from_raw(raw, rec, mask=mask)
