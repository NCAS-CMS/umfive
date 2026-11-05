import csv
import re
from importlib.resources import files
from pathlib import PosixPath

# Matches numeric value and optional exponent; mirrors cf loader behavior.
_NUMBER_REGEX = r"([-+]?\d*\.?\d+(e[-+]?\d+)?)"

# Column indices in STASH_to_CF.txt
_SUBMODEL = 0
_STASH = 1
_NAME = 2
_UNITS = 3
_VALID_FROM = 4
_VALID_TO = 5
_STANDARD_NAME = 6
_CF_EXTRA = 7
_PP_EXTRA = 8

# The default STASH table
_default_stash_table = {}

# The current STASH table
_stash_table = {}


def _parse_version(value):
    """Parse UM versions from the STASH table source.

    .. versionadded:: 0.3.0

    :Parameters:

        value: `str`
            The UM version from the STASH table source.

    :Returns:

        `float` or `None`
            The parsed version, which will a `float`, or `None` of the
            input *value* cannot be converted to a `float`.

    :Examples:

    >>> _parse_version('503')
    503.0

    >>> print(_parse_version(''))
    None

    """
    if not value:
        return

    try:
        return float(value)
    except ValueError:
        return


def _parse_cf_extra(value):
    """Parse CF extra information from the STASH table source.

    .. versionadded:: 0.3.0

    :Parameters:

        value: `str`
            The CF extra information from the STASH table source.

    :Returns:

        `dict`
            A dictionary containing the extra inormation.

    :Examples:

    >>> _parse_cf_extra('height=1.5m')
    {'height': ['1.5', 'm']}

    >>> _parse_cf_extra('where_sea_ice')
    {'where': 'where sea_ice'}

    """
    out = {}
    if not value:
        return out

    for token in value.split():
        if token.startswith("height="):
            out["height"] = re.split(
                _NUMBER_REGEX, token, flags=re.IGNORECASE
            )[1:4:2]
        elif token.startswith("below_"):
            out["below"] = re.split(_NUMBER_REGEX, token, flags=re.IGNORECASE)[
                1:4:2
            ]
        elif token.startswith("where_"):
            out["where"] = token.replace("where_", "where ", 1)
        elif token.startswith("over_"):
            out["over"] = token.replace("over_", "over ", 1)

    return out


def load_stash_table(table=None, delimiter="!", merge=True, reset=False):
    """Load a STASH-to-CF table from a file.

    Each mapping is defined by a separate line in a text file. Each
    line contains nine ``!``-delimited entries:

    0. Submodel: UM sub model identifier (1 = atmosphere, 2 = ocean,
       etc.)
    1. STASH: STASH code (e.g. 3236)
    2. STASHmaster description:STASH name as given in the STASHmaster
       files
    3. Units: Units of this STASH code (e.g. 'kg m-2')
    4. Valid from: This STASH valid from this UM version (e.g. 405)
    5. Valid to: This STASH valid to this UM version (e.g. 501)
    6. CF standard name: The CF standard name
    7. CF info: Anything useful (such as standard name modifiers)
    8. PP conditions: PP conditions which need to be satisfied for
       this translation

    Only entries "Submodel", "STASH", and "CF standard name" are
    mandatory, all other entries may be left blank. For example,
    ``1!999!!!!!ultraviolet_index!!`` is a valid mapping from
    atmosphere STASH code 999 to the standard name ultraviolet_index.

    If the "Valid from" and "Valid to" entries are omitted then the
    STASH-to-CF mapping is assumed to apply to all UM versions.

    .. versionadded:: 0.3.0

    .. seealso:: `add_stash_record`, `stash_records`, `stash_table`

    :Parameters:

        table: `str` or `None`, optional
            Use the conversion table at this file location. If `None`
            (the default) the table in ``data/STASH_to_CF.txt`` will be
            used.

        delimiter: `str`, optional
            The delimiter of the table columns. By default, ``!`` is
            taken as the delimiter.

        merge: `bool`, optional
            If False then the table is updated to only contain the
            mappings defined by the *table* parameter. By default the
            mappings defined by the *table* parameter are incorporated
            into the existing table, overwriting any entries which
            already exist.

        reset: `bool`, optional
            If True then clear all entries and re-load the default
            table.

    :Returns:

        `None`

    :Examples:

    >>> load_stash_table()
    >>> load_stash_table('my_table.txt')
    >>> load_stash_table('my_table2.txt', ',')
    >>> load_stash_table('my_table3.txt', merge=True)
    >>> load_stash_table('my_table4.txt', merge=False)

    """
    if reset:
        table = None
        merge = False
        _stash_table.clear()

    if table is None:
        # Use the default STASH table
        if _default_stash_table:
            # Use the existing default tables
            read_table = False
            store_default = False
        else:
            read_table = True
            store_default = True

        table_path = files(__package__).joinpath("data/STASH_to_CF.txt")
    else:
        # User supplied table
        read_table = True
        store_default = False
        table_path = PosixPath(table)

    stash2sn = {}
    if read_table:
        with table_path.open("r", encoding="utf-8") as handle:
            rows = list(
                csv.reader(handle, delimiter=delimiter, skipinitialspace=True)
            )

        for row in rows:
            if not row or row[0].startswith("#"):
                continue

            # Normalize to expected width.
            if len(row) < 9:
                row = row + [""] * (9 - len(row))

            key = (int(row[_SUBMODEL]), int(row[_STASH]))
            name = row[_NAME]
            units = row[_UNITS] or None
            valid_from = _parse_version(row[_VALID_FROM])
            valid_to = _parse_version(row[_VALID_TO])
            standard_name = row[_STANDARD_NAME] or None
            cf_info = _parse_cf_extra(row[_CF_EXTRA])
            pp_extra = row[_PP_EXTRA].rstrip()

            entry = (
                name,
                units,
                valid_from,
                valid_to,
                standard_name,
                cf_info,
                pp_extra,
            )

            if key in stash2sn:
                stash2sn[key] += (entry,)
            else:
                stash2sn[key] = (entry,)

    if reset:
        stash2sn = _default_stash_table

    if store_default:
        # Store the default STASH table
        _default_stash_table.update(stash2sn)

    if not merge:
        _stash_table.clear()

    _stash_table.update(stash2sn)


def stash_table(reset=False):
    """Return a copy of the current STASH-to-CF table.

    .. versionadded:: 0.3.0

    .. seealso:: `add_stash_record`, `load_stash_table`, `stash_record`

    :Parameters:

        reset: `bool`, optional
            If True then clear all entries, re-load the default
            table, and return it.

    :Returns:

        `dict`
            The currently loaded STASH table.

    """
    if reset or not _default_stash_table:
        load_stash_table(reset=reset)

    return _stash_table.copy()


def stash_records(submodel, stash_code):
    """Return the STASH-to-CF records for a particular STASH code.

    .. versionadded:: 0.3.0

    .. seealso:: `add_stash_record`, `load_stash_table`, `stash_table`

    :Parameters:

        submodel: `int`
            The submodel of the STASH code (e.g. ``2``).

        stash: `int`
            The STASH code (e.g. ``101``).

    :Returns:

        `tuple`
            The STASH records from the currently loaded STASH table
            for the given *submodel* and *stash_code*.

    :Examples:

    >>> stash_records(2, 101)
    (('POTENTIAL TEMPERATURE (OCEAN)  DEG.C', 'K @ 273.15',  None,  900.0, 'sea_water_potential_temperature', {}, ''),)

    >>> stash_records(1, 5)
    (('THETAL IN THE EXTERNAL DUMP         ', 'K', None, 407.0, None, {}, ''),
     ('OROGRAPHIC GRADIENT  X COMPONENT    ', None, 606.0, None, None, {}, ''))

    """
    if not _stash_table:
        load_stash_table()

    return _stash_table.get((int(submodel), int(stash_code)), ())


def add_stash_record(
    submodel,
    stash_code,
    name,
    units=None,
    valid_from=None,
    valid_to=None,
    standard_name=None,
    cf_info=None,
    pp_extra="",
):
    """Add a new STASH record to the STASH-to-CF table in memory.

    .. versionadded:: 0.5.0

    .. seealso:: `load_stash_table`, `stash_records`, `stash_table`

    :Parameters:

        submodel: `int`
            The submodel of the STASH code (e.g. ``1``).

        stash_code: `int`
            The STASH code (e.g. ``3209``).

        name: `str`
            The description of the STASH code.

        units: `str`, optional
            The physical units of the STASH code.

        valid_from: `float` or `str`, optional
            The UM version from which the STASH code is valid.

        valid_to: `float` or `str`, optional
            The UM version until which the STASH code is valid.

        standard_name: `str`, optional
            The CF standard name.

        cf_info: `dict` or `str`, optional
            Additional CF attributes or conditions.

        pp_extra: `str`, optional
            PP conditions which need to be satisfied.

    :Returns:

        `None`

    :Examples:

    >>> add_stash_record(
    ...     3, 999, 'MY WATER TABLE DEPTH', 'm',
    ...     standard_name='water_table_depth'
    ... )

    """
    if not _stash_table:
        load_stash_table()

    key = (int(submodel), int(stash_code))

    valid_from = _parse_version(valid_from)
    valid_to = _parse_version(valid_to)

    if cf_info is None:
        cf_info = {}
    elif isinstance(cf_info, str):
        cf_info = _parse_cf_extra(cf_info)

    entry = (
        name,
        units,
        valid_from,
        valid_to,
        standard_name,
        cf_info,
        pp_extra,
    )

    if key in _stash_table:
        _stash_table[key] += (entry,)
    else:
        _stash_table[key] = (entry,)
