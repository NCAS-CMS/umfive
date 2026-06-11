from ..constants import INDEX_LBEGIN, N_HDR
from .extra_data import read_extra_data
from .header import decode_header_from_bytes
from .interpret import get_extra_data_offset_and_length, get_ff_disk_length
from .models import RecordInfo


def _read_flh_word(reader, word_index, word_size, byte_order):
    """Read a fixed length header (FLH) word.

    :Parameter:

        reader: `ByteReader`
            The file reader.

        word_index: `int`
            The index of the word in the FLH (starting at 1).

        word_size: `int`
            The word size (``4`` or ``8``).

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

    :Returns:

        `int`
            The value of the FLH word.

    """
    offset = word_index * word_size
    raw = reader.read_at(offset, word_size)
    if len(raw) != word_size:
        raise ValueError(
            f"Short read while reading fixed length header index "
            f"{word_index}: "
            f"Expected {word_size} bytes, got {len(raw)} bytes"
        )

    return int.from_bytes(raw, byteorder=byte_order, signed=True)


def _read_fortran_record_len(reader, pos, word_size, byte_order):
    """The size in bytes of a header or data record.

    The size is gleaned by reading the associated block control word
    (BCW) that gives the size in bytes of the associated header or
    data record. For instance, the BCW for a 32-bit header containing
    64 words is 256 (=64*4).

    :Parameter:

        reader: `ByteReader`
            The file reader.

        pos: `int`
            The byte address of the block control word (BCW) at the
            start of the record.

        word_size: `int`
            The word size (``4`` or ``8``).

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

    :Returns:

        `int`
            The record size.

    """
    raw = reader.read_at(pos, word_size)
    if len(raw) == 0:
        return

    if len(raw) != word_size:
        raise ValueError(
            f"Short read on fortran record length at byte address {pos}: "
            f"Expected 0 or {word_size} bytes, got {len(raw)} bytes"
        )

    return int.from_bytes(raw, byteorder=byte_order, signed=True)


def _skip_fortran_record(reader, pos, word_size, byte_order):
    """The size of a record, and the address of the next record.

    The record may be a header record or data record. If the record is
    a header record then the next record is a data record, and vice
    versa.

    :Parameter:

        reader: `ByteReader`
            The file reader.

        pos: `int`
            The byte address of the block control word (BCW) at the
            start of the record.

        word_size: `int`
            The word size (``4`` or ``8``).

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

    :Returns:

        `int`, `int`
             The size in bytes of the header or data record, and the
             byte address of the BCW at the start of the next (data or
             header) record.

    """
    rec_bytes = _read_fortran_record_len(reader, pos, word_size, byte_order)
    if rec_bytes is None:
        return

    trailer_pos = pos + word_size + rec_bytes
    trailer = _read_fortran_record_len(
        reader, trailer_pos, word_size, byte_order
    )
    if trailer is None or trailer != rec_bytes:
        raise ValueError(
            "Corrupt fortran record: leading/trailing lengths differ: "
            f"Expected {trailer} bytes, got {rec_bytes} bytes"
        )

    return rec_bytes, trailer_pos + word_size


def scan_pp_headers(reader, file_type):
    """Read all records from a PP file.

    :Parameter:

        reader: `ByteReader`
            The file reader.

        file_type: `FileTypeInfo`
            File-type information for the file.

    :Returns:

        `list` of `RecordInfo`
            The records.

    """
    if file_type.fmt != "PP":
        raise ValueError("scan_pp_headers requires PP file type")

    recs: list[RecordInfo] = []
    word_size = file_type.word_size
    byte_order = file_type.byte_order

    pos = 0
    while True:
        first = _skip_fortran_record(reader, pos, word_size, byte_order)
        if first is None:
            break

        header_record_len, after_header = first
        if header_record_len != N_HDR * word_size:
            raise ValueError(
                "Unsupported PP header length: "
                f"{header_record_len // word_size} words"
            )

        header_offset = pos + word_size
        header_bytes = reader.read_at(header_offset, header_record_len)
        int_hdr, real_hdr = decode_header_from_bytes(
            header_bytes, word_size=word_size, byte_order=byte_order
        )

        data = _skip_fortran_record(
            reader, after_header, word_size, byte_order
        )
        if data is None:
            raise ValueError(
                "Corrupt PP file: missing data record after header"
            )

        data_record_len, after_data = data
        data_offset = after_header + word_size

        # Read any extra data and parse it into a dictionary
        extra_data_offset, extra_data_length = (
            get_extra_data_offset_and_length(
                int_hdr, data_offset, data_record_len, word_size
            )
        )
        extra_data = read_extra_data(
            reader,
            extra_data_offset,
            extra_data_length,
            word_size,
            byte_order,
        )

        recs.append(
            RecordInfo(
                int_hdr=int_hdr,
                real_hdr=real_hdr,
                header_offset=header_offset,
                data_offset=data_offset,
                disk_length=data_record_len,
                extra_data=extra_data,
                word_size=word_size,
                byte_order=byte_order,
            )
        )
        pos = after_data

    return recs


def scan_ff_headers(reader, file_type):
    """Read all records from a fields file.

    :Parameter:

        reader: `ByteReader`
            The file reader.

        file_type: `FileTypeInfo`
            File-type information for the file.

    :Returns:

        `list` of `RecordInfo`
            The records.

    """
    if file_type.fmt != "FF":
        raise ValueError("scan_ff_headers requires FF file type")

    word_size = file_type.word_size
    byte_order = file_type.byte_order

    # Kept for parity with C read path; currently not otherwise used.
    _read_flh_word(reader, 4, word_size, byte_order)

    start_lookup = _read_flh_word(reader, 149, word_size, byte_order)
    nlookup1 = _read_flh_word(reader, 150, word_size, byte_order)
    nlookup2 = _read_flh_word(reader, 151, word_size, byte_order)
    start_data = _read_flh_word(reader, 159, word_size, byte_order)

    if nlookup1 < N_HDR:
        raise ValueError(f"Unsupported header length: {nlookup1} words")

    hdr_start = (start_lookup - 1) * word_size
    hdr_size = nlookup1 * word_size
    n_raw_rec = nlookup2

    valid: list[bool] = []
    for i in range(n_raw_rec):
        lbbegin_offset = (
            hdr_start + (i * hdr_size) + (INDEX_LBEGIN * word_size)
        )
        raw = reader.read_at(lbbegin_offset, word_size)
        if len(raw) != word_size:
            raise ValueError(
                "Short read while checking FF valid record markers"
            )

        lbbegin = int.from_bytes(raw, byteorder=byte_order, signed=True)
        valid.append(lbbegin != -99)

    recs: list[RecordInfo] = []
    data_offset_calculated = (start_data - 1) * word_size

    for i in range(n_raw_rec):
        if not valid[i]:
            continue

        header_offset = hdr_start + (i * hdr_size)
        header_bytes = reader.read_at(header_offset, hdr_size)
        if len(header_bytes) < N_HDR * word_size:
            raise ValueError("Short read while reading FF lookup header")

        int_hdr, real_hdr = decode_header_from_bytes(
            header_bytes, word_size=word_size, byte_order=byte_order
        )

        disk_length = get_ff_disk_length(int_hdr, word_size)
        data_offset_specified = int(int_hdr[INDEX_LBEGIN]) * word_size
        data_offset = (
            data_offset_specified
            if data_offset_specified != 0
            else data_offset_calculated
        )
        data_offset_calculated += disk_length

        # Read any extra data and parse it into a dictionary
        extra_data_offset, extra_data_length = (
            get_extra_data_offset_and_length(
                int_hdr, data_offset, disk_length, word_size
            )
        )
        if extra_data_length:
            extra_data = read_extra_data(
                reader,
                extra_data_offset,
                extra_data_length,
                word_size,
                byte_order,
            )
        else:
            extra_data = None

        recs.append(
            RecordInfo(
                int_hdr=int_hdr,
                real_hdr=real_hdr,
                header_offset=header_offset,
                data_offset=data_offset,
                disk_length=disk_length,
                extra_data=extra_data,
                word_size=word_size,
                byte_order=byte_order,
            )
        )

    return recs
