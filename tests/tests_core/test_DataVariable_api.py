import numpy as np

import ppfive


def test_DataVariable_attributes():
    f = ppfive.File("tests/data/test2.pp")
    name = f.data_variables[0]
    v = f[name]
    assert v.name == name
    assert v.attrs == {
        "DIMENSION_LIST": (
            ("time",),
            ("air_pressure",),
            ("grid_latitude",),
            ("grid_longitude",),
        ),
        "_FillValue": np.float32(-1.0737418e09),
        "cell_methods": "time: mean",
        "coordinates": "time air_pressure grid_latitude grid_longitude",
        "grid_mapping": "rotated_latitude_longitude",
        "lbcode": "101",
        "lbproc": "128",
        "lbtim": "121",
        "lbvc": "8",
        "long_name": "U COMPNT OF WIND ON PRESSURE LEVELS",
        "missing_value": np.float32(-1.0737418e09),
        "runid": "aaacf",
        "source": "UM",
        "standard_name": "eastward_wind",
        "stash_code": "15201",
        "submodel": "1",
        "um_identity": "UM_m01s15i201_vn405",
        "um_stash_source": "m01s15i201",
        "um_version": "4.5",
        "units": "m s-1",
    }
    assert v.shape == (3, 5, 110, 106)
    assert v.dtype == np.float32
    assert v.chunks == (1, 1, 110, 106)
    assert v.data_loader_options == {
        "thread_count": 0,
        "cat_range_allowed": False,
    }
    assert v.file is f
    assert len(v.chunk_records) == 15


def test_DataVariableID_attributes():
    f = ppfive.File("tests/data/wgdos_packed.pp")
    name = f.data_variables[0]
    v = f[name]
    assert v.id.chunks == (1, 1, 145, 192)
    assert v.id.dtype == "float32"
    assert v.id.first_chunk == (0, 0, 0, 0)
    assert v.id.shape == (1, 1, 145, 192)
    assert v.id.index == {
        (0, 0, 0, 0): ppfive.core.models.StoreInfo(
            chunk_offset=(0, 0, 0, 0),
            filter_mask=0,
            byte_offset=268,
            size=60232,
        )
    }


def test_DataVariable__getitem__():
    f = ppfive.File("tests/data/test2.pp")
    v = f[f.data_variables[0]]

    assert np.allclose(
        v[:, :, 0, 0],
        np.array(
            [
                [-0.12850454, 9.911384, 25.353613, 49.802994, 1.9440817],
                [2.9332578, 11.721181, 25.39008, 39.663734, 1.1223084],
                [1.6628141, 9.238531, 21.56609, 27.310707, -0.70770234],
            ],
            dtype="float32",
        ),
    )

    assert np.allclose(
        v[::2, ::2, 0, 0],
        np.array(
            [
                [-0.12850454, 25.353613, 1.9440817],
                [1.6628141, 21.56609, -0.70770234],
            ],
            dtype="float32",
        ),
    )

    assert np.allclose(
        v[::-1, ::-1, 0, 0],
        np.array(
            [
                [-0.70770234, 27.310707, 21.56609, 9.238531, 1.6628141],
                [1.1223084, 39.663734, 25.39008, 11.721181, 2.9332578],
                [1.9440817, 49.802994, 25.353613, 9.911384, -0.12850454],
            ],
            dtype="float32",
        ),
    )

    assert np.allclose(
        v[::-2, ::-2, 0, 0],
        np.array(
            [
                [-0.70770234, 21.56609, 1.6628141],
                [1.9440817, 25.353613, -0.12850454],
            ],
            dtype="float32",
        ),
    )

    assert np.allclose(
        v[::-2, [0, 1, 4], 0, 0],
        np.array(
            [
                [1.6628141, 9.238531, -0.70770234],
                [-0.12850454, 9.911384, 1.9440817],
            ],
            dtype="float32",
        ),
    )
