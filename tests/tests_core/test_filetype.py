import numpy as np

from umfive import LocalPosixReader
from umfive.core import detect_file_type


def test_detect_file_type_pp32_le(tmp_path):
    p = tmp_path / "pp32.bin"
    data = np.zeros(28, dtype="<i4")
    data[0] = 64 * 4
    data[1] = 2026
    p.write_bytes(data.tobytes())

    with LocalPosixReader(p) as reader:
        file_type = detect_file_type(reader)

    assert file_type.fmt == "PP"
    assert file_type.word_size == 4
    assert file_type.byte_order == "little"


def test_detect_file_type_ff32_le(tmp_path):
    p = tmp_path / "ff32.bin"
    data = np.zeros(28, dtype="<i4")
    data[1] = 1
    p.write_bytes(data.tobytes())

    with LocalPosixReader(p) as reader:
        file_type = detect_file_type(reader)

    assert file_type.fmt == "FF"
    assert file_type.word_size == 4
    assert file_type.byte_order == "little"
