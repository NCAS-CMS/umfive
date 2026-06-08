from pathlib import Path

import fsspec
import numpy as np
import pytest

from ppfive import File
from ppfive.io.fsspec_reader import FsspecReader


def _data_variable_names(f: File) -> list[str]:
    return [
        name
        for name, variable in f.variables.items()
        if variable.attrs.get("CLASS")
        not in (b"DIMENSION_SCALE", b"AUXILIARY_COORDINATE")
        and "grid_mapping_name" not in variable.attrs
    ]


def test_fsspec_reader_read_at(tmp_path: Path):
    p = tmp_path / "data.bin"
    p.write_bytes(b"abcdefghij")

    fs = fsspec.filesystem("file")
    with FsspecReader(fs, str(p)) as reader:
        assert reader.read_at(2, 4) == b"cdef"


def test_file_can_parse_via_fsspec_reader():
    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"
    fs = fsspec.filesystem("file")

    with FsspecReader(fs, str(path)) as reader:
        f = File(str(path), reader=reader)
        names = _data_variable_names(f)
        assert names
        arr = f[names[0]][:]

    assert arr.shape == (3, 5, 110, 106)
    assert arr.dtype == np.dtype("float32")


def _read_all_variables(
    path: Path, *, use_fsspec: bool
) -> dict[str, np.ndarray]:
    if use_fsspec:
        fs = fsspec.filesystem("file")
        with FsspecReader(fs, str(path)) as reader:
            with File(str(path), reader=reader) as f:
                names = _data_variable_names(f)
                return {name: np.asarray(f[name][:]) for name in names}

    with File(str(path)) as f:
        names = _data_variable_names(f)
        return {name: np.asarray(f[name][:]) for name in names}


@pytest.mark.parametrize(
    "fixture_name",
    [
        "test2.pp",  # PP format fixture
        "cl_umfile",  # Fields File (FF) fixture
    ],
)
def test_full_read_parity_local_vs_fsspec(fixture_name: str):
    path = Path(__file__).resolve().parents[1] / "data" / fixture_name

    local = _read_all_variables(path, use_fsspec=False)
    via_fsspec = _read_all_variables(path, use_fsspec=True)

    assert list(via_fsspec) == list(local)

    for name in local:
        lhs = via_fsspec[name]
        rhs = local[name]
        assert lhs.shape == rhs.shape
        assert lhs.dtype == rhs.dtype
        assert np.array_equal(
            lhs, rhs
        ), f"fsspec mismatch for {fixture_name} variable {name}"
