from contextlib import redirect_stdout
from io import StringIO

import pytest

import umfive


def test_DataVariable_lookup_header():
    f = umfive.File("tests/data/test.pp")
    name = next(iter(f.data_variables))
    v = f[name]

    # Test single header string return
    header_str = v.lookup_header(n=0, display=False)
    assert isinstance(header_str, str)
    assert "Lookup header 1 of 15" in header_str
    assert "LBYR: 1979" in header_str

    # Test negative index
    header_last = v.lookup_header(n=-1, display=False)
    assert "Lookup header 15 of 15" in header_last

    # Test 'all'
    all_headers = v.lookup_header(n="all", display=False)
    assert all_headers.count("Lookup header") == 15

    # Test display=True (stdout)
    buf = StringIO()
    with redirect_stdout(buf):
        v.lookup_header(n=0, display=True)

    assert "Lookup header 1 of 15" in buf.getvalue()

    # Test invalid index
    with pytest.raises(ValueError):
        v.lookup_header(n=100)


def test_DataVariable_lookup_header_items():
    f = umfive.File("tests/data/test.pp")
    name = next(iter(f.data_variables))
    v = f[name]

    # Test list return
    items = v.lookup_header_items(display=False)
    assert isinstance(items, dict)
    assert len(items) == 64
    assert items["LBYR"] == [1979] * 15

    for item in ("LBYRD", "lbyrd", ["LBYRD"]):
        items = v.lookup_header_items(item, display=False)
        assert isinstance(items, dict)
        assert len(items) == 1
        assert items["LBYRD"] == [1979] * 15

    for item in ("LBYRD", "lbyrd", ["LBYRD"]):
        items = v.lookup_header_items(["LBMON", "lbyr"], display=False)
        assert isinstance(items, dict)
        assert len(items) == 2
        assert items["LBMON"] == [5] * 15
        assert items["LBYR"] == [1979] * 15

    # Test display=True (stdout)
    buf = StringIO()
    with redirect_stdout(buf):
        v.lookup_header_items(display=True)

    output = buf.getvalue()
    assert "LBYR: [1979, 1979" in output
    assert "BMDI: [-1073741824.0" in output
