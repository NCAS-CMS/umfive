from umfive import stash_records


def test_stash_table_has_expected_entry_1():
    records = stash_records(1, 1)
    assert len(records) == 1

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
    assert valid_from is None
    assert standard_name == "surface_air_pressure"
    assert cf_info == {}
    assert pp_extra == ""


def test_stash_table_has_expected_entry_2():
    records = stash_records(1, 2)
    assert len(records) == 2

    (
        long_name,
        units,
        valid_from,
        valid_to,
        standard_name,
        cf_info,
        pp_extra,
    ) = records[0]

    assert long_name.strip() == "U COMPNT OF WIND AFTER TIMESTEP"
    assert units == "m s-1"
    assert valid_to is None
    assert valid_from is None
    assert standard_name == "eastward_wind"
    assert cf_info == {}
    assert pp_extra == "true_latitude_longitude"

    (
        long_name,
        units,
        valid_from,
        valid_to,
        standard_name,
        cf_info,
        pp_extra,
    ) = records[1]

    assert long_name.strip() == "U COMPNT OF WIND AFTER TIMESTEP"
    assert units == "m s-1"
    assert valid_to is None
    assert valid_from is None
    assert standard_name == "x_wind"
    assert cf_info == {}
    assert pp_extra == "rotated_latitude_longitude"


def test_stash_table_has_expected_entry_3():
    records = stash_records(1, 3236)
    assert len(records) == 1

    (
        long_name,
        units,
        valid_from,
        valid_to,
        standard_name,
        cf_info,
        pp_extra,
    ) = records[0]

    assert long_name.strip() == "TEMPERATURE AT 1.5M"
    assert units == "K"
    assert valid_to is None
    assert valid_from is None
    assert standard_name == "air_temperature"
    assert cf_info == {"height": ["1.5", "m"]}
    assert pp_extra == ""


def test_stash_table_has_expected_entry_4():
    records = stash_records(1, 5)
    assert len(records) == 2

    (
        long_name,
        units,
        valid_from,
        valid_to,
        standard_name,
        cf_info,
        pp_extra,
    ) = records[0]

    assert long_name.strip() == "THETAL IN THE EXTERNAL DUMP"
    assert units == "K"
    assert valid_to == 407.0
    assert valid_from is None
    assert standard_name is None
    assert cf_info == {}
    assert pp_extra == ""

    (
        long_name,
        units,
        valid_from,
        valid_to,
        standard_name,
        cf_info,
        pp_extra,
    ) = records[1]

    assert long_name.strip() == "OROGRAPHIC GRADIENT  X COMPONENT"
    assert units is None
    assert valid_to is None
    assert valid_from == 606.0
    assert standard_name is None
    assert cf_info == {}
    assert pp_extra == ""
