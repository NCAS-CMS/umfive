from pathlib import Path

import pytest

from ppfive import File, LocalPosixReader


def test_LocalPosixReader_read_at(tmp_path: Path):
    p = tmp_path / "data.bin"
    p.write_bytes(b"abcdefghij")

    with LocalPosixReader(p) as reader:
        assert reader.read_at(2, 4) == b"cdef"


def test_local_reader_reopens_after_close(tmp_path: Path):
    p = tmp_path / "sample.bin"
    p.write_bytes(b"abcdef")

    reader = LocalPosixReader(p)
    assert reader.read_at(1, 3) == b"bcd"
    reader.close()

    # Should transparently reopen and still serve absolute reads.
    assert reader.read_at(2, 2) == b"cd"
    reader.close()


def test_LocalPosixReader_fs_protocol():
    with LocalPosixReader("tests/data/test2.pp") as f:
        assert f.fs.protocol == "file"


@pytest.mark.parametrize(
    "path",
    [
        "tests/data/test2.pp",
        Path("tests/data/test2.pp"),
    ],
)
def test_LocalPosixReader_as_input_to_File(path):
    with LocalPosixReader(path) as reader:
        f = File(reader)
        assert (
            repr(f)
            == "<ppfive.File: tests/data/test2.pp, 1 data variable, 9 metadata variables>"
        )
