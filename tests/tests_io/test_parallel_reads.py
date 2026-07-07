from pathlib import Path

import fsspec
import numpy as np

import umfive


def _first_data_variable_name(f: umfive.File) -> str:
    return f.data_variables[0]


def test_local_parallel_matches_serial():
    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with umfive.File(str(path)) as f_serial:
        name = _first_data_variable_name(f_serial)
        serial = f_serial[name][:]

    with umfive.File(str(path)) as f_parallel:
        f_parallel.set_parallelism(max_thread_count=4)
        name = _first_data_variable_name(f_parallel)
        parallel = f_parallel[name][:]

    assert np.allclose(parallel, serial, rtol=1e-6, atol=1e-6)


def test_fsspec_bulk_range_matches_serial_for_unpacked_data():
    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with umfive.File(str(path)) as f_serial:
        f_serial.set_parallelism(max_thread_count=0, cat_range_allowed=False)
        name = _first_data_variable_name(f_serial)
        serial = f_serial[name][:]

    file_like = fsspec.filesystem("file").open(str(path), "rb")
    with umfive.File(file_like) as f_parallel:
        f_parallel.set_parallelism(max_thread_count=4, cat_range_allowed=True)
        name = _first_data_variable_name(f_parallel)
        parallel = f_parallel[name][:]

    assert np.allclose(parallel, serial, rtol=1e-6, atol=1e-6)


def test_fsspec_bulk_range_matches_serial_for_wgdos_packed_data():
    path = Path(__file__).resolve().parents[1] / "data" / "wgdos_packed.pp"

    with umfive.File(str(path)) as f_serial:
        name = _first_data_variable_name(f_serial)
        serial = f_serial[name][:]

    file_like = fsspec.filesystem("file").open(str(path), "rb")
    with umfive.File(file_like) as f_parallel:
        f_parallel.set_parallelism(max_thread_count=4, cat_range_allowed=True)
        name = _first_data_variable_name(f_parallel)
        parallel = f_parallel[name][:]

    assert np.allclose(parallel, serial, rtol=1e-6, atol=1e-6)


def test_local_parallel_slice_matches_serial():
    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with umfive.File(str(path)) as f_serial:
        name = _first_data_variable_name(f_serial)
        serial = f_serial[name][0, :, :, :]

    with umfive.File(str(path)) as f_parallel:
        f_parallel.set_parallelism(max_thread_count=4)
        name = _first_data_variable_name(f_parallel)
        parallel = f_parallel[name][0, :, :, :]

    assert np.allclose(parallel, serial, rtol=1e-6, atol=1e-6)


def test_fsspec_bulk_range_slice_matches_serial_for_unpacked_data():
    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with umfive.File(str(path)) as f_serial:
        name = _first_data_variable_name(f_serial)
        serial = f_serial[name][0, :, :, :]

    file_like = fsspec.filesystem("file").open(str(path), "rb")
    with umfive.File(file_like) as f_parallel:
        f_parallel.set_parallelism(max_thread_count=4, cat_range_allowed=True)
        name = _first_data_variable_name(f_parallel)
        parallel = f_parallel[name][0, :, :, :]

    assert np.allclose(parallel, serial, rtol=1e-6, atol=1e-6)
