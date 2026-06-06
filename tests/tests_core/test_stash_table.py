from ppfive.core.stash_table import stash_records


def test_stash_table_has_expected_entry():
    records = stash_records(1, 1)
    assert records

    (
        long_name,
        units,
        valid_from,
        valid_to,
        standard_name,
        cf_info,
        pp_extra,
    ) = records[0]

    assert long_name.strip() == "PSTAR AFTER TIMESTEP"
    assert units == "Pa"
    assert valid_to == 407.0
    assert standard_name == "surface_air_pressure"
    assert cf_info == {}
    assert pp_extra == ""
