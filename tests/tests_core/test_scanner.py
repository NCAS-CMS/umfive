import numpy as np

from ppfive.core.constants import (
    INDEX_LBBEGIN,
    INDEX_LBLREC,
    INDEX_LBPACK,
    N_INT_HDR,
    N_REAL_HDR,
)
from ppfive.core.models import FileTypeInfo
from ppfive.core.scanner import scan_ff_headers, scan_pp_headers
from ppfive.io.local import LocalPosixReader


def _fortran_record(
    payload: bytes, word_size: int = 4, endian: str = "little"
) -> bytes:
    n = len(payload)
    return (
        n.to_bytes(word_size, byteorder=endian, signed=True)
        + payload
        + n.to_bytes(word_size, byteorder=endian, signed=True)
    )


def test_scan_pp_headers_single_record(tmp_path):
    int_hdr = np.zeros(N_INT_HDR, dtype="<i4")
    real_hdr = np.zeros(N_REAL_HDR, dtype="<f4")
    int_hdr[INDEX_LBLREC] = 3
    int_hdr[INDEX_LBPACK] = 0

    header_payload = int_hdr.tobytes() + real_hdr.tobytes()
    data_payload = np.array([1.0, 2.0, 3.0], dtype="<f4").tobytes()

    blob = _fortran_record(header_payload) + _fortran_record(data_payload)

    p = tmp_path / "one.pp"
    p.write_bytes(blob)

    with LocalPosixReader(p) as reader:
        recs = scan_pp_headers(
            reader,
            FileTypeInfo(fmt="PP", byte_ordering="little_endian", word_size=4),
        )

    assert len(recs) == 1
    rec = recs[0]
    assert rec.header_offset == 4
    assert rec.data_offset == 268
    assert rec.disk_length == 12
    assert int(rec.int_hdr[INDEX_LBLREC]) == 3


def test_scan_ff_headers_single_lookup(tmp_path):
    word_size = 4
    fixed = np.zeros(300, dtype="<i4")
    fixed[149] = 161  # start_lookup (1-based)
    fixed[150] = 64  # nlookup1
    fixed[151] = 1  # nlookup2
    fixed[159] = 225  # start_data (1-based)

    int_hdr = np.zeros(N_INT_HDR, dtype="<i4")
    real_hdr = np.zeros(N_REAL_HDR, dtype="<f4")
    int_hdr[INDEX_LBLREC] = 3
    int_hdr[INDEX_LBPACK] = 0
    int_hdr[INDEX_LBBEGIN] = 0

    lookup = int_hdr.tobytes() + real_hdr.tobytes()

    # start_lookup=161 -> offset 640 bytes, start_data=225 -> offset 896 bytes
    blob = bytearray(max(896 + 12, len(fixed.tobytes())))
    blob[: len(fixed.tobytes())] = fixed.tobytes()
    blob[640 : 640 + len(lookup)] = lookup
    blob[896 : 896 + 12] = np.array([7.0, 8.0, 9.0], dtype="<f4").tobytes()

    p = tmp_path / "one.ff"
    p.write_bytes(bytes(blob))

    with LocalPosixReader(p) as reader:
        recs = scan_ff_headers(
            reader,
            FileTypeInfo(fmt="FF", byte_ordering="little_endian", word_size=4),
        )

    assert len(recs) == 1
    rec = recs[0]
    assert rec.header_offset == 640
    assert rec.data_offset == 896
    assert rec.disk_length == 12
