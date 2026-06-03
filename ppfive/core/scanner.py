from __future__ import annotations

from ppfive.io.base import ByteReader

from .constants import INDEX_LBBEGIN, N_HDR
from .header import decode_header_from_bytes
from .interpret import get_ff_disk_length, get_extra_data_offset_and_length
from .models import FileTypeInfo, RecordInfo
from .extra_data import ExtraDataUnpacker

def _read_word(reader: ByteReader, word_index: int, word_size: int, byte_ordering: str) -> int:
    offset = word_index * word_size
    raw = reader.read_at(offset, word_size)
    if len(raw) != word_size:
        raise ValueError("Short read while reading fixed header word")

    endian = "little" if byte_ordering == "little_endian" else "big"
    return int.from_bytes(raw, byteorder=endian, signed=True)


def _read_fortran_record_len(reader: ByteReader, pos: int, word_size: int, byte_ordering: str):
    raw = reader.read_at(pos, word_size)
    if len(raw) == 0:
        return None
    if len(raw) != word_size:
        raise ValueError("Short read on fortran record length")

    endian = "little" if byte_ordering == "little_endian" else "big"
    return int.from_bytes(raw, byteorder=endian, signed=True)


def _skip_fortran_record(reader: ByteReader, pos: int, word_size: int, byte_ordering: str):
    rec_bytes = _read_fortran_record_len(reader, pos, word_size, byte_ordering)
    if rec_bytes is None:
        return None

    trailer_pos = pos + word_size + rec_bytes
    trailer = _read_fortran_record_len(reader, trailer_pos, word_size, byte_ordering)
    if trailer is None or trailer != rec_bytes:
        raise ValueError("Corrupt fortran record: leading/trailing lengths differ")

    return rec_bytes, trailer_pos + word_size


def scan_pp_headers(reader: ByteReader, file_type: FileTypeInfo) -> list[RecordInfo]:
    if file_type.fmt != "PP":
        raise ValueError("scan_pp_headers requires PP file type")

    recs: list[RecordInfo] = []
    word_size = file_type.word_size
    byte_ordering = file_type.byte_ordering

    pos = 0
    while True:
        first = _skip_fortran_record(reader, pos, word_size, byte_ordering)
        if first is None:
            break

        header_record_len, after_header = first
        if header_record_len != N_HDR * word_size:
            raise ValueError(
                f"Unsupported PP header length: {header_record_len // word_size} words"
            )

        header_offset = pos + word_size
        header_bytes = reader.read_at(header_offset, header_record_len)
        int_hdr, real_hdr = decode_header_from_bytes(
            header_bytes, word_size=word_size, byte_ordering=byte_ordering
        )

        data = _skip_fortran_record(reader, after_header, word_size, byte_ordering)
        if data is None:
            raise ValueError("Corrupt PP file: missing data record after header")

        data_record_len, after_data = data
        data_offset = after_header + word_size

        extra_data_offset, extra_data_length = (
            get_extra_data_offset_and_length(
                int_hdr, data_offset, data_record_len, word_size
            )
        )

        extra_data = read_extra_data(reader, 
            extra_data_offset, extra_data_length, word_size, byte_ordering
        )
        
        recs.append(
            RecordInfo(
                int_hdr=int_hdr,
                real_hdr=real_hdr,
                header_offset=header_offset,
                data_offset=data_offset,
                disk_length=data_record_len,
                extra_data=extra_data
            )
        )
        pos = after_data

    return recs


def scan_ff_headers(reader: ByteReader, file_type: FileTypeInfo) -> list[RecordInfo]:
    if file_type.fmt != "FF":
        raise ValueError("scan_ff_headers requires FF file type")

    word_size = file_type.word_size
    byte_ordering = file_type.byte_ordering

    # Kept for parity with C read path; currently not otherwise used.
    _ = _read_word(reader, 4, word_size, byte_ordering)

    start_lookup = _read_word(reader, 149, word_size, byte_ordering)
    nlookup1 = _read_word(reader, 150, word_size, byte_ordering)
    nlookup2 = _read_word(reader, 151, word_size, byte_ordering)
    start_data = _read_word(reader, 159, word_size, byte_ordering)

    if nlookup1 < N_HDR:
        raise ValueError(f"Unsupported header length: {nlookup1} words")

    hdr_start = (start_lookup - 1) * word_size
    hdr_size = nlookup1 * word_size
    n_raw_rec = nlookup2

    valid: list[bool] = []
    for i in range(n_raw_rec):
        lbbegin_offset = hdr_start + (i * hdr_size) + (INDEX_LBBEGIN * word_size)
        raw = reader.read_at(lbbegin_offset, word_size)
        if len(raw) != word_size:
            raise ValueError("Short read while checking FF valid record markers")
        endian = "little" if byte_ordering == "little_endian" else "big"
        lbbegin = int.from_bytes(raw, byteorder=endian, signed=True)
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
            header_bytes, word_size=word_size, byte_ordering=byte_ordering
        )

        disk_length = get_ff_disk_length(int_hdr, word_size)
        data_offset_specified = int(int_hdr[INDEX_LBBEGIN]) * word_size
        data_offset = data_offset_specified if data_offset_specified != 0 else data_offset_calculated
        data_offset_calculated += disk_length

        recs.append(
            RecordInfo(
                int_hdr=int_hdr,
                real_hdr=real_hdr,
                header_offset=header_offset,
                data_offset=data_offset,
                disk_length=disk_length,
            )
        )

    return recs

def read_extra_data(
        reader, extra_data_offset,  extra_data_length, word_size, byte_ordering
):
    
    raw_extra_data = reader.read_at(extra_data_offset,  extra_data_length)
    extra = ExtraDataUnpacker(raw_extra_data , word_size, byte_ordering)
    return extra.get_data()
