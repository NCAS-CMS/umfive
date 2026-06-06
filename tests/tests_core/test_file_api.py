import logging

import numpy as np

from ppfive import File


def test_file_iterates_variable_names():
    f = File(
        __file__,
        variable_index={
            "temp": {
                "shape": (2, 2),
                "dtype": "f8",
                "chunk_shape": (1, 2),
                "attrs": {"units": "K"},
                "data_loader": lambda: np.array([[1.0, 2.0], [3.0, 4.0]]),
            }
        },
    )

    data_names = [
        name
        for name, variable in f.variables.items()
        if variable.attrs.get("CLASS") != b"DIMENSION_SCALE"
    ]
    assert data_names == ["temp"]
    assert "temp" in list(f)
    v = f["temp"]
    assert v.shape == (2, 2)
    assert v.dtype == np.dtype("float64")
    assert v.chunk_shape == (1, 2)
    assert v.chunks == (1, 2)
    assert v.attrs["units"] == "K"
    assert np.all(v[:] == np.array([[1.0, 2.0], [3.0, 4.0]]))
    assert len(v) == 2
    assert v.len() == 2
    assert v.value.shape == (2, 2)
    assert v.parent is f
    assert v.file is f
    assert "shape (2, 2)" in repr(v)


def test_variable_dataset_like_helpers():
    f = File(
        __file__,
        variable_index={
            "temp": {
                "shape": (2, 2),
                "dtype": "f8",
                "chunk_shape": (1, 1),
                "data_loader": lambda: np.array([[1.25, 2.25], [3.25, 4.25]]),
            }
        },
    )

    v = f["temp"]
    target = np.empty((2, 2), dtype="f8")
    v.read_direct(target)
    assert np.allclose(target, np.array([[1.25, 2.25], [3.25, 4.25]]))

    with v.astype("f4"):
        cast = v[:]

    assert cast.dtype == np.dtype("float32")
    assert v.id.shape == (2, 2)
    assert v.id.dtype == np.dtype("float64")
    assert list(v.iter_chunks()) == [
        (slice(0, 1, 1), slice(0, 1, 1)),
        (slice(0, 1, 1), slice(1, 2, 1)),
        (slice(1, 2, 1), slice(0, 1, 1)),
        (slice(1, 2, 1), slice(1, 2, 1)),
    ]
    assert v.dims is None


def test_get_lazy_view_falls_back_with_log(caplog):
    f = File(
        __file__,
        variable_index={"x": {"data_loader": lambda: np.array([1, 2])}},
    )

    with caplog.at_level(logging.INFO):
        view = f.get_lazy_view("x")

    assert view is f["x"]
    assert "get_lazy_view is not supported" in caplog.text


def test_file_normalizes_variable_paths():
    f = File(
        __file__,
        variable_index={
            "temp": {
                "shape": (1,),
                "dtype": "f8",
                "data_loader": lambda: np.array([1.0]),
            }
        },
    )

    assert np.allclose(f["temp"][:], np.array([1.0]))
    assert np.allclose(f["/temp"][:], np.array([1.0]))

    try:
        _ = f["./temp"]
    except KeyError:
        # posix normpath strips ./, but this branch protects against regressions.
        assert False, "Expected ./temp to resolve to temp"

    try:
        _ = f["group/temp"]
        assert False, "Expected nested path lookup to fail"
    except KeyError:
        pass


def test_set_parallelism_validation():
    f = File(
        __file__,
        variable_index={
            "temp": {
                "shape": (1,),
                "dtype": "f8",
                "data_loader": lambda: np.array([1.0]),
            }
        },
    )

    f.set_parallelism(thread_count=0)
    f.set_parallelism(thread_count=3, cat_range_allowed=False)

    try:
        f.set_parallelism(thread_count=-1)
        assert False, "Expected negative thread_count to raise"
    except ValueError:
        pass
