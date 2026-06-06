import numpy as np

from ppfive.constants import (
    INDEX_BMDI,
    INDEX_LBCODE,
    INDEX_LBLREC,
    INDEX_LBLEV,
    INDEX_LBNPT,
    INDEX_LBPACK,
    INDEX_LBROW,
    INDEX_LBUSER4,
    INDEX_LBUSER7,
    N_INT_HDR,
    N_REAL_HDR,
)
from ppfive.core.data import read_record_array
from ppfive.core.models import RecordInfo
from ppfive.io.local import LocalPosixReader


def _record(
    raw: bytes, int_hdr, real_hdr, tmp_path, name: str
) -> tuple[LocalPosixReader, RecordInfo]:
    path = tmp_path / name
    path.write_bytes(raw)
    reader = LocalPosixReader(path)
    rec = RecordInfo(
        int_hdr=int_hdr,
        real_hdr=real_hdr,
        header_offset=0,
        data_offset=0,
        disk_length=len(raw),
    )
    return reader, rec


def _headers(pack: int, lblrec: int = 4):
    int_hdr = np.zeros(N_INT_HDR, dtype="<i4")
    real_hdr = np.zeros(N_REAL_HDR, dtype="<f4")
    int_hdr[INDEX_LBUSER4] = 16004
    int_hdr[INDEX_LBUSER7] = 1
    int_hdr[INDEX_LBCODE] = 1
    int_hdr[INDEX_LBROW] = 2
    int_hdr[INDEX_LBNPT] = 2
    int_hdr[INDEX_LBLEV] = 1
    int_hdr[INDEX_LBLREC] = lblrec
    int_hdr[INDEX_LBPACK] = pack
    real_hdr[INDEX_BMDI] = -1.0e30
    return int_hdr, real_hdr


def test_cray32_packed_record_reads(tmp_path):
    int_hdr, real_hdr = _headers(pack=2, lblrec=4)
    raw = np.array([1.5, 2.5, 3.5, 4.5], dtype="<f4").tobytes()
    reader, rec = _record(raw, int_hdr, real_hdr, tmp_path, "pack2.bin")

    try:
        arr = read_record_array(
            reader, rec, word_size=4, byte_ordering="little_endian"
        )
    finally:
        reader.close()

    assert np.allclose(arr, np.array([1.5, 2.5, 3.5, 4.5], dtype="float32"))


def test_run_length_packed_record_reads(tmp_path):
    int_hdr, real_hdr = _headers(pack=4, lblrec=6)
    mdi = real_hdr[INDEX_BMDI]
    raw = np.array([1.0, mdi, 2.0, 5.0, 6.0, 7.0], dtype="<f4").tobytes()
    reader, rec = _record(raw, int_hdr, real_hdr, tmp_path, "pack4.bin")

    try:
        arr = read_record_array(
            reader, rec, word_size=4, byte_ordering="little_endian"
        )
    finally:
        reader.close()

    assert np.allclose(arr, np.array([1.0, mdi, mdi, 5.0], dtype="float32"))
