"""Tests for umfive.File accepting a raw seekable file-like object.

pyfive.File accepts any object that has .read and .seek methods and uses
it directly (duck-typing).  umfive.File should behave the same way so
that callers do not need to know about ByteReader / FsspecReader
internals -- they can simply open a file (e.g. via fsspec) and pass the
handle straight to umfive.File.

"""

from pathlib import Path

import fsspec
import numpy as np
import pytest

from umfive import File, FileObjReader

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PP_PATH = DATA_DIR / "test2.pp"


def test_FileObjReader_fs_protocol():
    file_like = fsspec.filesystem("file").open("tests/data/test2.pp", "rb")
    with FileObjReader(file_like) as f:
        assert "file" in f.fs.protocol


@pytest.mark.parametrize(
    "path",
    [
        "tests/data/test2.pp",
        Path("tests/data/test2.pp"),
    ],
)
def test_file_accepts_local_reader_as_first_argument(path):
    file_like = fsspec.filesystem("file").open(path, "rb")
    with FileObjReader(file_like) as reader:
        f = File(reader)
        assert (
            repr(f)
            == f"<umfive.File: {file_like.name}, 1 data variable, 9 metadata variables>"
        )


def test_FileObjReader_rejects_object_without_seek():
    """An object with .read but no .seek should raise ValueError."""

    class _NoSeek:
        def read(self, n=-1):
            return b""

    with pytest.raises((ValueError, TypeError)):
        File(_NoSeek())


def test_fileobj_parity_with_path():
    """Reading via a raw fsspec handle should return identical data to
    path-based open."""
    with File(PP_PATH) as f_path:
        expected = {
            name: np.asarray(f_path[name][:]) for name in f_path.data_variables
        }

    fs = fsspec.filesystem("file")
    with fs.open(str(PP_PATH), "rb") as fh:
        f_fh = File(fh)
        result = {
            name: np.asarray(f_fh[name][:]) for name in f_fh.data_variables
        }

    assert list(result) == list(expected)
    for name in expected:
        np.testing.assert_array_equal(result[name], expected[name])
