import pytest

import ppfive


def test_File_get_set_parallelsm():
    f = ppfive.File("tests/data/cl_umfile")
    assert (
        f.set_parallelism(max_thread_count=100, cat_range_allowed=False)
        is None
    )
    assert f.get_parallelism() == {
        "UM_m01s00i001_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s00i002_vn405_true_latitude_longitude": {
            "thread_count": 100,
            "cat_range_allowed": False,
        },
        "UM_m01s00i003_vn405_true_latitude_longitude": {
            "thread_count": 100,
            "cat_range_allowed": False,
        },
        "UM_m01s00i010_vn405": {
            "thread_count": 100,
            "cat_range_allowed": False,
        },
        "UM_m01s00i023_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s00i031_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s00i032_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s00i033_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s01i201_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s01i207_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s01i208_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s01i209_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s01i210_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s01i211_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s01i235_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s02i201_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s02i205_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s02i206_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s02i207_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s02i208_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s02i260_vn405": {
            "thread_count": 100,
            "cat_range_allowed": False,
        },
        "UM_m01s03i217_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s03i223_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s03i234_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s03i236_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s03i238_vn405": {
            "thread_count": 48,
            "cat_range_allowed": False,
        },
        "UM_m01s03i337_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s04i203_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s04i204_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s05i201_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s05i202_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s05i214_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s05i215_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s08i023_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s08i202_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s08i223_vn405": {
            "thread_count": 48,
            "cat_range_allowed": False,
        },
        "UM_m01s08i225_vn405": {
            "thread_count": 48,
            "cat_range_allowed": False,
        },
        "UM_m01s08i229_vn405": {
            "thread_count": 48,
            "cat_range_allowed": False,
        },
        "UM_m01s08i230_vn405": {
            "thread_count": 48,
            "cat_range_allowed": False,
        },
        "UM_m01s08i231_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s08i234_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s08i235_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s08i392_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s08i394_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s08i432_vn405": {
            "thread_count": 48,
            "cat_range_allowed": False,
        },
        "UM_m01s09i217_vn405": {
            "thread_count": 12,
            "cat_range_allowed": False,
        },
        "UM_m01s15i201_vn405": {
            "thread_count": 100,
            "cat_range_allowed": False,
        },
        "UM_m01s15i202_vn405": {
            "thread_count": 100,
            "cat_range_allowed": False,
        },
        "UM_m01s16i203_vn405": {
            "thread_count": 100,
            "cat_range_allowed": False,
        },
    }

    with pytest.raises(ValueError):
        f.set_parallelism(max_thread_count=-1)


def test_File__repr__():
    f = ppfive.File("tests/data/test2.pp")
    assert (
        repr(f)
        == "<ppfive.File: tests/data/test2.pp, 1 data variable, 9 metadata variables>"
    )


def test_File__str__():
    f = ppfive.File("tests/data/test2.pp")
    assert (
        str(f)
        == """<ppfive.File: tests/data/test2.pp, 1 data variable, 9 metadata variables>
Data variables:
    UM_m01s15i201_vn405: <ppfive.DataVariable: UM_m01s15i201_vn405, shape=(3, 5, 110, 106), dimensions=(time, air_pressure, grid_latitude, grid_longitude)>
Metadata variables:
    time: <ppfive.DimensionScale: time, shape=(3,)>
    bounds2: <ppfive.DimensionScale: bounds2, size=2>
    time_bounds: <ppfive.Variable: time_bounds, shape=(3, 2), dimensions=(time, bounds2)>
    air_pressure: <ppfive.DimensionScale: air_pressure, shape=(5,)>
    grid_latitude: <ppfive.DimensionScale: grid_latitude, shape=(110,)>
    grid_latitude_bounds: <ppfive.Variable: grid_latitude_bounds, shape=(110, 2), dimensions=(grid_latitude, bounds2)>
    grid_longitude: <ppfive.DimensionScale: grid_longitude, shape=(106,)>
    grid_longitude_bounds: <ppfive.Variable: grid_longitude_bounds, shape=(106, 2), dimensions=(grid_longitude, bounds2)>
    rotated_latitude_longitude: <ppfive.Variable: rotated_latitude_longitude, shape=(), dimensions=()>"""
    )


def test_File_consolidated_metadata():
    f = ppfive.File("tests/data/cl_umfile")
    assert f.consolidated_metadata

    f = ppfive.File("tests/data/wgdos_packed.pp")
    assert f.consolidated_metadata

    f = ppfive.File("tests/data/test2.pp")
    assert not f.consolidated_metadata

    f = ppfive.File("tests/data/extra_data.pp")
    assert not f.consolidated_metadata


def test_File_has_extra_data():
    f = ppfive.File("tests/data/extra_data.pp")
    assert f.has_extra_data

    f = ppfive.File("tests/data/test2.pp")
    assert not f.has_extra_data


def test_File_userblock_size():
    f = ppfive.File("tests/data/wgdos_packed.pp")
    assert f.userblock_size == 0


def test_File_close():
    f = ppfive.File("tests/data/wgdos_packed.pp")
    assert f.close() is None
    assert f["UM_m01s30i201_vn1100"][0, 0, 0, 0] == -3.0783691


def test_File_get_lazy_view():
    f = ppfive.File("tests/data/wgdos_packed.pp")
    name = f.data_variables[0]
    assert f.get_lazy_view(name) is f[name]


def test_File__items__():
    f = ppfive.File("tests/data/wgdos_packed.pp")
    assert len(f.items()) == len(f.variables.items())


def test_File__init__attribues():
    f = ppfive.File("tests/data/wgdos_packed.pp")
    assert f.filename == "tests/data/wgdos_packed.pp"
    assert f.mode == "r"
    assert f.parent is None
    assert f.name == "/"
    assert f.path == "/"
    assert f.attrs == {"Conventions": ppfive.constants.CF_CONVENTIONS}
    assert f.groups == {}
    assert f.dimensions == {}


def test_File__getitem__():
    f = ppfive.File("tests/data/test2.pp")
    name = f.data_variables[0]
    var = f.variables[name]
    assert f[name] is var
    assert f[f".{name}"] is var
    assert f[f"./{name}"] is var
    assert f[f"{name}/"] is var
    assert f[f"./{name}/"] is var

    for n in ("____bad_name", f"{name}//", f"{name}/other", f"{name}/other/"):
        with pytest.raises(KeyError):
            f[n]
