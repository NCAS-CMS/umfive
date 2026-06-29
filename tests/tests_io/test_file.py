from io import BytesIO
from pathlib import Path

import pytest

import ppfive


@pytest.mark.parametrize(
    "dataset, suffix",
    [
        ("cl_umfile", ""),
        ("test2", ".pp"),
        ("extra_data", ".pp"),
        ("umfile", ".pp"),
        ("wgdos_packed", ".pp"),
    ],
)
def test_file(dataset, suffix):
    # Build the file paths dynamically based on parameters
    input_file = f"tests/data/{dataset}{suffix}"
    dump_file = f"tests/data/{dataset}_dump.txt"

    with ppfive.File(input_file) as f:
        with open(dump_file, "r") as d:
            dump_contents = d.read()
            assert (
                f.dump(display=False, data=True).rstrip()
                == dump_contents.rstrip()
            )


def test_File_with_builtin_open_as_input():
    with open("tests/data/test2.pp", "rb") as fh:
        f = ppfive.File(fh)
        assert (
            repr(f)
            == "<ppfive.File: tests/data/test2.pp, 1 data variable, 9 metadata variables>"
        )


def test_File_with_bytesio_as_input():
    path = Path("tests/data/test2.pp")
    raw = BytesIO(path.read_bytes())
    f = ppfive.File(raw)
    assert (
        repr(f)
        == "<ppfive.File: <file-like>, 1 data variable, 9 metadata variables>"
    )


@pytest.mark.parametrize(
    "filename",
    [[], {}, (), None, 0, 3.14, True],
)
def test_File_with_invalid_input(filename):
    with pytest.raises(ValueError):
        ppfive.File(filename)


def test_File_with_directory_input():
    with pytest.raises(IsADirectoryError):
        ppfive.File("tests/data")
