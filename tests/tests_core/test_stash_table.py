from umfive import add_stash_record, stash_records


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


def test_add_stash_record():
    # Add a new record
    add_stash_record(
        submodel=3,
        stash_code=999,
        name="MY WATER TABLE DEPTH",
        units="m",
        valid_from="10.1",
        valid_to=None,
        standard_name="water_table_depth",
        cf_info="height=1.5m",
        pp_extra="some_extra"
    )

    records = stash_records(3, 999)
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

    assert long_name == "MY WATER TABLE DEPTH"
    assert units == "m"
    assert valid_from == 10.1
    assert valid_to is None
    assert standard_name == "water_table_depth"
    assert cf_info == {"height": ["1.5", "m"]}
    assert pp_extra == "some_extra"

    # Add another record to the same submodel/stash_code to test appending
    add_stash_record(
        submodel=3,
        stash_code=999,
        name="MY WATER TABLE DEPTH 2",
        units="cm",
    )

    records = stash_records(3, 999)
    assert len(records) == 2
    
    (
        long_name_2,
        units_2,
        valid_from_2,
        valid_to_2,
        standard_name_2,
        cf_info_2,
        pp_extra_2,
    ) = records[1]

    assert long_name_2 == "MY WATER TABLE DEPTH 2"
    assert units_2 == "cm"
    assert valid_from_2 is None
    assert valid_to_2 is None
    assert standard_name_2 is None
    assert cf_info_2 == {}
    assert pp_extra_2 == ""
