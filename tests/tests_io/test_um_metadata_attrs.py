import pytest

from ppfive import File


def test_cf_like_um_attrs_for_release2_fixture():
    with File("tests/data/cl_umfile") as f:
        v = f["UM_m01s00i001_vn405"]
        attrs = v.attrs

    assert attrs["um_stash_source"] == "m01s00i001"
    assert attrs["um_identity"] == "UM_m01s00i001_vn405"
    assert attrs["um_version"] == "4.5"
    assert attrs["standard_name"] == "surface_air_pressure"
    assert attrs["long_name"] == "PSTAR AFTER TIMESTEP"
    assert attrs["units"] == "Pa"
    assert attrs["source"] == "UM"


@pytest.mark.skip(reason="File is too big for GitHub")
def test_cf_like_um_attrs_for_release3_fixture():
    with File("tests/data/dk922a.pa1983aug") as f:
        v = f["UM_m01s00i024_vn1305"]
        attrs = v.attrs

    assert attrs["um_stash_source"] == "m01s00i024"
    assert attrs["um_identity"] == "UM_m01s00i024_vn1305"
    assert attrs["um_version"] == "13.5"
    assert attrs["standard_name"] == "surface_temperature"
    assert attrs["long_name"] == "SURFACE TEMPERATURE AFTER TIMESTEP"
    assert attrs["units"] == "K"
