from __future__ import annotations

import csv
import re
from importlib.resources import files
from pathlib import PosixPath

# Matches numeric value and optional exponent; mirrors cf loader behavior.
_NUMBER_REGEX = r"([-+]?\d*\.?\d+(e[-+]?\d+)?)"

# Column indices in STASH_to_CF.txt
_MODEL = 0
_STASH = 1
_NAME = 2
_UNITS = 3
_VALID_FROM = 4
_VALID_TO = 5
_STANDARD_NAME = 6
_CF_EXTRA = 7
_PP_EXTRA = 8

# The STASH table
_stash_table = {}


def _parse_version(value: str):
    if not value:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def _parse_cf_extra(value: str) -> dict[str, object]:
    out: dict[str, object] = {}
    if not value:
        return out

    for token in value.split():
        if token.startswith("height="):
            out["height"] = re.split(_NUMBER_REGEX, token, re.IGNORECASE)[
                1:4:2
            ]
        elif token.startswith("below_"):
            out["below"] = re.split(_NUMBER_REGEX, token, re.IGNORECASE)[1:4:2]
        elif token.startswith("where_"):
            out["where"] = token.replace("where_", "where ", 1)
        elif token.startswith("over_"):
            out["over"] = token.replace("over_", "over ", 1)

    return out


def load_stash_table(table=None, delimiter="!", merge=True):
    """Load a STASH to standard name conversion table from a file.

    This used when reading PP and UM fields files.

    Each mapping is defined by a separate line in a text file. Each
    line contains nine ``!``-delimited entries:

    0. ID: UM sub model identifier (1 = atmosphere, 2 = ocean, etc.)
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

    Only entries "ID", "STASH", and "CF standard name" are mandatory,
    all other entries may be left blank. For example,
    ``1!999!!!!!ultraviolet_index!!`` is a valid mapping from
    atmosphere STASH code 999 to the standard name
    ultraviolet_index.

    If the "Valid from" and "Valid to" entries are omitted then the
    stash mapping is assumed to apply to all UM versions.

    :Parameters:

        table: `str`, optional
            Use the conversion table at this file location. By default
            the table in ``data/STASH_to_CF.txt`` will be used.

            Setting *table* to `None` will reset the table, removing
            any modifications that have previously been made.

        delimiter: `str`, optional
            The delimiter of the table columns. By default, ``!`` is
            taken as the delimiter.

        merge: `bool`, optional
            If False then the table is updated to only contain the
            mappings defined by the *table* parameter. By default the
            mappings defined by the *table* parameter are incorporated
            into the existing table, overwriting any entries which
            already exist.

            If *table* is `None` then *merge* is taken as False,
            regardless of its given value.

    :Returns:

        `dict`
            The new STASH to standard name conversion table.

    **Examples**

    >>> load_stash_table()
    >>> load_stash_table('my_table.txt')
    >>> load_stash_table('my_table2.txt', ',')
    >>> load_stash_table('my_table3.txt', merge=True)
    >>> load_stash_table('my_table4.txt', merge=False)

    """
    if table is None:
        # Use default conversion table
        merge = False
        table_path = files("ppfive").joinpath("data/STASH_to_CF.txt")
    else:
        # User supplied table
        table_path = PosixPath(table)

    stash2sn = {}

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

        key = (int(row[_MODEL]), int(row[_STASH]))
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

    if not merge:
        _stash_table.clear()

    _stash_table.update(stash2sn)


def stash_table():
    """Return a copy of the loaded STASH to standard name conversion
    table.

    .. seealso:: `load_stash_table`, `stash_table_record`

    """
    if not _stash_table:
        load_stash_table()

    return _stash_table.copy()


def stash_records(submodel=None, stash_code=None):
    """Return STASH records."""
    if not _stash_table:
        load_stash_table()

    if submodel is None and stash_code is None:
        return _stash_table.copy()

    return _stash_table.get((int(submodel), int(stash_code)), ())
