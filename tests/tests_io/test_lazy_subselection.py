from pathlib import Path

import numpy as np

import ppfive.io.chunk_read as chunk_read_module
from ppfive import File


def _first_data_variable_name(f: File) -> str:
    return next(name for name in f.data_variables)


def test_subselection_reads_only_intersecting_chunks(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with File(str(path)) as f:
        name = _first_data_variable_name(f)
        v = f[name]

        calls = []
        original = chunk_read_module.read_record_array

        def _counting_read(reader, rec):
            calls.append(int(rec.data_offset))
            return original(reader, rec)

        monkeypatch.setattr(
            chunk_read_module, "read_record_array", _counting_read
        )

        sub_one = np.asarray(v[0, 0, :, :])
        assert sub_one.shape == (110, 106)
        assert len(calls) == 1

        calls.clear()
        sub_five = np.asarray(v[0, :, :, :])
        assert sub_five.shape == (5, 110, 106)
        assert len(calls) == 5

        # Re-reading the same slice should read the same required chunks again.
        calls.clear()
        sub_five_again = np.asarray(v[0, :, :, :])
        assert sub_five_again.shape == (5, 110, 106)
        assert len(calls) == 5

        # Reading a subset should read exactly one chunk.
        calls.clear()
        sub_cached = np.asarray(v[0, 1, :, :])
        assert sub_cached.shape == (110, 106)
        assert len(calls) == 1

        # A full read goes through chunk reads (3t × 5z = 15 chunks).
        calls.clear()
        full = np.asarray(v[:])
        assert full.shape == v.shape
        assert len(calls) == 15

        # No internal cache: a subsequent slice re-reads its chunks.
        calls.clear()
        sub_after_full = np.asarray(v[0, 0, :, :])
        assert sub_after_full.shape == (110, 106)
        assert len(calls) == 1
