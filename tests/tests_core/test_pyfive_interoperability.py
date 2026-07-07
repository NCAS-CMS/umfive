import pytest

import umfive


def test_pyfive_resistration():
    pyfive = pytest.importorskip("pyfive")

    with umfive.File("tests/data/test2.pp") as f:
        assert isinstance(f, pyfive.File)

        for var in f.values():
            assert isinstance(var, pyfive.Dataset)


def test_umfive_file_exposes_pyfive_root_members():
    pyfive = pytest.importorskip("pyfive")

    with umfive.File("tests/data/test2.pp") as f:
        assert isinstance(f, pyfive.File)
        assert isinstance(f.attrs, dict)
        assert isinstance(f.groups, dict)
        assert isinstance(f.variables, dict)
        assert isinstance(f.dimensions, dict)
        assert f.name == "/"
        assert f.path == "/"

        # Dimensions
        dim_like = [
            name for name, var in f.items() if "_Netcdf4Dimid" in var.attrs
        ]
        assert set(dim_like) == set(
            (
                "time",
                "bounds2",
                "air_pressure",
                "grid_latitude",
                "grid_longitude",
            )
        )
