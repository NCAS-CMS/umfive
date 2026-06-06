"""Tests for ppfive.File accepting a raw seekable file-like object.

pyfive.File accepts any object that has .read and .seek methods and uses it
directly (duck-typing).  ppfive.File should behave the same way so that callers
do not need to know about ByteReader / FsspecReader internals -- they can simply
open a file (e.g. via fsspec) and pass the handle straight to ppfive.File.
"""

from io import BytesIO
from pathlib import Path

import fsspec
import numpy as np
import pytest

from ppfive import File


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PP_PATH = DATA_DIR / "test2.pp"


def _data_variable_names(f: File) -> list[str]:
    return [
        name
        for name, variable in f.variables.items()
        if variable.attrs.get("CLASS")
        not in (b"DIMENSION_SCALE", b"AUXILIARY_COORDINATE")
        and "grid_mapping_name" not in variable.attrs
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MinimalFileObj:
    """Bare-minimum seekable/readable wrapper around an in-memory buffer."""

    def __init__(self, data: bytes) -> None:
        self._buf = BytesIO(data)

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._buf.seek(offset, whence)

    # deliberately no .close() to ensure that is optional


# ---------------------------------------------------------------------------
# Tests: plain file-like objects
# ---------------------------------------------------------------------------


def test_file_accepts_raw_open_builtin():
    """ppfive.File should accept a built-in open() handle (has .read and .seek)."""
    with open(PP_PATH, "rb") as fh:
        f = File(fh)
        names = _data_variable_names(f)
        assert names
        arr = f[names[0]][:]

    assert arr.shape == (3, 5, 110, 106)
    assert arr.dtype == np.dtype("float32")


def test_file_accepts_bytesio():
    """ppfive.File should accept a BytesIO instance."""
    data = PP_PATH.read_bytes()
    buf = BytesIO(data)
    f = File(buf)
    names = _data_variable_names(f)
    assert names
    arr = f[names[0]][:]
    assert arr.shape == (3, 5, 110, 106)


def test_file_accepts_minimal_fileobj():
    """ppfive.File should work with any object that has .read and .seek."""
    data = PP_PATH.read_bytes()
    fobj = _MinimalFileObj(data)
    f = File(fobj)
    names = _data_variable_names(f)
    assert names


def test_file_rejects_object_without_seek():
    """An object with .read but no .seek should raise ValueError."""

    class _NoSeek:
        def read(self, n=-1):
            return b""

    with pytest.raises((ValueError, TypeError)):
        File(_NoSeek())


# ---------------------------------------------------------------------------
# Tests: fsspec file handles passed directly (the primary use-case)
# ---------------------------------------------------------------------------


def test_file_accepts_fsspec_local_handle():
    """ppfive.File should accept an fsspec local-filesystem open handle directly,
    without the caller needing to construct a FsspecReader."""
    fs = fsspec.filesystem("file")
    with fs.open(str(PP_PATH), "rb") as fh:
        f = File(fh)
        names = _data_variable_names(f)
        assert names
        arr = f[names[0]][:]

    assert arr.shape == (3, 5, 110, 106)
    assert arr.dtype == np.dtype("float32")


def test_fileobj_parity_with_path():
    """Reading via a raw fsspec handle should return identical data to path-based open."""
    with File(PP_PATH) as f_path:
        expected = {
            name: np.asarray(f_path[name][:])
            for name in _data_variable_names(f_path)
        }

    fs = fsspec.filesystem("file")
    with fs.open(str(PP_PATH), "rb") as fh:
        f_fh = File(fh)
        result = {
            name: np.asarray(f_fh[name][:])
            for name in _data_variable_names(f_fh)
        }

    assert list(result) == list(expected)
    for name in expected:
        np.testing.assert_array_equal(result[name], expected[name])
