from __future__ import annotations

import re
from contextlib import redirect_stdout
from io import StringIO

import pytest

from ppfive.ppdump import main as ppdump_main


def _run_ppdump(path: str) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        rc = ppdump_main([path])

    assert rc == 0
    return buf.getvalue()


def _run_p5dump(path: str) -> str:
    pytest.importorskip("pyfive")
    from pyfive.p5dump import main as p5dump_main

    buf = StringIO()
    with redirect_stdout(buf):
        rc = p5dump_main([path])

    assert rc == 0
    return buf.getvalue()


def _variable_names(dump_text: str) -> list[str]:
    names = []
    in_variables = False
    for line in dump_text.splitlines():
        stripped = line.strip()
        if stripped == "variables:":
            in_variables = True
            continue

        if in_variables and stripped.startswith("//"):
            break

        if not in_variables or not stripped or ":" in stripped:
            continue

        m = re.match(r"^(?:\w+\d*|char)\s+(\w+)\s*(?:\(|;)", stripped)
        if m:
            names.append(m.group(1))

    return names


def test_ppdump_matches_core_variable_names_with_p5dump_fixture():
    pp_out = _run_ppdump("tests/data/test2.pp")
    p5_out = _run_p5dump("tests/data/test2-viacf.nc")

    pp_vars = set(_variable_names(pp_out))
    p5_vars = set(_variable_names(p5_out))

    expected_core = {
        "time",
        "air_pressure",
        "grid_latitude",
        "grid_longitude",
        "UM_m01s15i201_vn405",
    }

    # ppfive fixture has no bounds variables, but core variables should align.
    assert expected_core.issubset(pp_vars)
    assert expected_core.issubset(p5_vars)


def test_ppdump_help_and_special_flag():
    assert ppdump_main(["-h"]) == 0
    assert ppdump_main(["-s", "tests/data/test2.pp"]) == 0


def test_ppdump_time_axis_metadata_matches_expected():
    out = _run_ppdump("tests/data/test2.pp")

    assert "float64 time(time) ;" in out
    assert 'time:axis = "T" ;' in out
    assert 'time:standard_name = "time" ;' in out
    assert 'time:units = "days since 1979-1-1" ;' in out
    assert 'time:calendar = "gregorian" ;' in out
    assert 'UM_m01s15i201_vn405:cell_methods = "time: mean" ;' in out
