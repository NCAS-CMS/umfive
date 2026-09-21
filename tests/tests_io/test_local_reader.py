import os
from pathlib import Path

import pytest

from umfive import File, LocalPosixReader


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


def test_local_reader_reopens_after_stale_fd(tmp_path: Path):
    p = tmp_path / "stale.bin"
    p.write_bytes(b"abcdefgh")

    reader = LocalPosixReader(p)
    assert reader.read_at(0, 2) == b"ab"

    # Simulate an externally invalidated descriptor while the reader still
    # holds a non-None fd value.
    stale_fd = reader._fd
    os.close(stale_fd)

    # Should recover from EBADF by reopening transparently and retrying.
    assert reader.read_at(2, 3) == b"cde"
    reader.close()


def test_LocalPosixReader_fs_protocol():
    with LocalPosixReader("tests/data/test.pp") as f:
        assert f.fs.protocol == "file"


@pytest.mark.parametrize(
    "path",
    [
        "tests/data/test.pp",
        Path("tests/data/test.pp"),
    ],
)
def test_LocalPosixReader_as_input_to_File(path):
    with LocalPosixReader(path) as reader:
        f = File(reader)
        assert (
            repr(f)
            == "tests/data/test.pp: <umfive.File: 1 data variable, 9 metadata variables>"
        )


def test_File_close_tolerates_stale_local_reader_fd():
    f = File("tests/data/test.pp")

    # Simulate external invalidation while File still owns the reader.
    stale_fd = f._reader._fd
    os.close(stale_fd)

    # This should be idempotent and not raise EBADF.
    f.close()
