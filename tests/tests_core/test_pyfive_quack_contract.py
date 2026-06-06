import pytest

from ppfive import File


def test_ppfive_file_exposes_pyfive_root_members():
    pyfive = pytest.importorskip("pyfive")

    with File("tests/data/test2.pp") as f:
        assert isinstance(f, pyfive.File)
        assert isinstance(f.attrs, dict)
        assert isinstance(f.groups, dict)
        assert isinstance(f.variables, dict)
        assert isinstance(f.dimensions, dict)
        assert f.name == "/"
        assert f.path == "/"
        dim_like = [
            name
            for name, _ in f.items()
            if name
            in ("time", "air_pressure", "grid_latitude", "grid_longitude")
            or name.startswith("dim_")
        ]
        assert dim_like


def test_ppfive_variable_registers_as_pyfive_dataset():
    pyfive = pytest.importorskip("pyfive")

    with File("tests/data/test2.pp") as f:
        v = f["m01s15i201"]
        assert isinstance(v, pyfive.Dataset)
        dim_name = next(
            name
            for name in dict(f.items())
            if name
            in ("time", "air_pressure", "grid_latitude", "grid_longitude")
            or name.startswith("dim_")
        )
        assert isinstance(f[dim_name], pyfive.Dataset)
