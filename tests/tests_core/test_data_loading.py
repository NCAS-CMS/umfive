import numpy as np

from ppfive import File
from ppfive.constants import (
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


def _fortran_record(
    payload: bytes, word_size: int = 4, endian: str = "little"
) -> bytes:
    n = len(payload)
    mark = n.to_bytes(word_size, byteorder=endian, signed=True)
    return mark + payload + mark


def _make_header(level: int) -> bytes:
    int_hdr = np.zeros(N_INT_HDR, dtype="<i4")
    real_hdr = np.zeros(N_REAL_HDR, dtype="<f4")

    int_hdr[INDEX_LBUSER4] = 16004
    int_hdr[INDEX_LBUSER7] = 1
    int_hdr[INDEX_LBCODE] = 1
    int_hdr[INDEX_LBROW] = 2
    int_hdr[INDEX_LBNPT] = 2
    int_hdr[INDEX_LBLREC] = 4
    int_hdr[INDEX_LBPACK] = 0
    int_hdr[INDEX_LBLEV] = level

    return int_hdr.tobytes() + real_hdr.tobytes()


def test_variable_loader_reads_data_and_reshapes(tmp_path):
    rec1 = _fortran_record(_make_header(1)) + _fortran_record(
        np.array([1.0, 2.0, 3.0, 4.0], dtype="<f4").tobytes()
    )
    rec2 = _fortran_record(_make_header(2)) + _fortran_record(
        np.array([5.0, 6.0, 7.0, 8.0], dtype="<f4").tobytes()
    )

    p = tmp_path / "two_levels.pp"
    p.write_bytes(rec1 + rec2)

    with File(str(p)) as f:
        names = [
            name
            for name, variable in f.variables.items()
            if variable.attrs.get("CLASS")
            not in (b"DIMENSION_SCALE", b"AUXILIARY_COORDINATE")
            and "grid_mapping_name" not in variable.attrs
        ]
        assert names == ["m01s16i004"]

        arr = f[names[0]][:]

    assert arr.shape == (1, 2, 2, 2)
    assert np.allclose(
        arr[0, 0], np.array([[5.0, 6.0], [7.0, 8.0]], dtype="float32")
    )
    assert np.allclose(
        arr[0, 1], np.array([[1.0, 2.0], [3.0, 4.0]], dtype="float32")
    )
