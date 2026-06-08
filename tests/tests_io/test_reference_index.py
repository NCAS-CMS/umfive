# from pathlib import Path
#
# import numpy as np
# import pytest
#
# from ppfive import File
# from ppfive.core import materialize_reference_dict
# from ppfive.io.local import LocalPosixReader
#
#
# @pytest.mark.parametrize(
#    "filename",
#    ["test2.pp", "wgdos_packed.pp"],
# )
# def test_reference_dict_materialization_matches_direct_read(filename):
#    path = Path(__file__).resolve().parents[1] / "data" / filename
#
#    with File(str(path)) as f:
#        name = next(
#            name
#            for name, variable in f.variables.items()
#            if variable.attrs.get("CLASS") != b"DIMENSION_SCALE"
#        )
#        variable = f[name]
#        direct = variable[:]
#        refs = variable.to_reference_dict()
#
#    with LocalPosixReader(path) as reader:
#        indexed = materialize_reference_dict(reader, refs)
#
#    assert indexed.shape == direct.shape
#    assert indexed.dtype == direct.dtype
#    assert np.allclose(indexed, direct, rtol=1e-6, atol=1e-6)
#
#
# def test_file_reference_dict_contains_variable_export():
#    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"
#
#    with File(str(path)) as f:
#        export = f.to_reference_dict()
#        name = next(
#            name
#            for name, variable in f.variables.items()
#            if variable.attrs.get("CLASS") != b"DIMENSION_SCALE"
#        )
#
#    assert export["version"] == 1
#    assert export["path"] == str(path)
#    assert name in export["variables"]
#    assert export["variables"][name]["refs"]
#    first_ref = next(iter(export["variables"][name]["refs"].values()))
#    assert "filter_mask" in first_ref
#    assert "data_offset" in first_ref
