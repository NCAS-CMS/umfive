from pathlib import Path

import cf
import numpy as np

from ppfive import File


def _canonical_stash_name(name: str) -> str:
    if name.startswith("UM_"):
        name = name[3:]
    if "_vn" in name:
        name = name.split("_vn", 1)[0]
    return name


def test_cf_reads_open_ppfive_file_and_matches_direct_pp_read():
    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with File(str(path)) as ppfive_file:
        via_ppfive = cf.read(ppfive_file)

    direct = cf.read(str(path))

    assert len(via_ppfive) == len(direct)

    for from_ppfive, from_path in zip(via_ppfive, direct):
        assert _canonical_stash_name(
            from_ppfive.nc_get_variable()
        ) == _canonical_stash_name(from_path.nc_get_variable())
        assert from_ppfive.array.shape == from_path.array.shape
        assert np.array_equal(
            np.asarray(from_ppfive.array),
            np.asarray(from_path.array),
        )


def test_cfdm_reads_open_ppfive_file_with_scalar_text_metadata():
    import cfdm

    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with File(str(path)) as ppfive_file:
        fields = cfdm.read(ppfive_file)

    assert len(fields) == 1
    field = fields[0]

    # Regression guard: these should be scalar strings, not character lists.
    assert field.get_property("standard_name") == "eastward_wind"
    assert field.get_property("units") == "m s-1"


def test_cfdm_reads_open_ppfive_file_with_semantic_dimension_names():
    import cfdm

    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with File(str(path)) as ppfive_file:
        fields = cfdm.read(ppfive_file)

    assert len(fields) == 1
    field = fields[0]
    representation = str(field)
    assert "time(3)" in representation
    assert "air_pressure(5)" in representation
    assert "grid_latitude(110)" in representation
    assert "grid_longitude(106)" in representation


def test_ppfive_iteration_exposes_coordinate_variables():
    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with File(str(path)) as f:
        names = list(f)

    assert "m01s15i201" in names
    assert "time" in names
    assert "air_pressure" in names
    assert "grid_latitude" in names
    assert "grid_longitude" in names
