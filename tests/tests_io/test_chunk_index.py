from pathlib import Path

import numpy as np

from ppfive import File


def test_variable_id_exposes_pyfive_like_chunk_index_for_unpacked_file():
    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with File(str(path)) as f:
        name = next(
            name
            for name, variable in f.variables.items()
            if variable.attrs.get("CLASS") != b"DIMENSION_SCALE"
        )
        variable = f[name]
        idx = variable.id.index

        assert variable.chunks == (1, 1, 110, 106)
        assert variable.id.get_num_chunks() == 15
        assert variable.id.first_chunk == (0, 0, 0, 0)

        info0 = variable.id.get_chunk_info(0)
        assert info0 == variable.id.get_chunk_info_by_coord((0, 0, 0, 0))
        assert info0.chunk_offset == (0, 0, 0, 0)
        assert info0.filter_mask == 0
        assert info0.byte_offset > 0
        assert info0.size == 110 * 106 * 4
        assert (0, 0, 0, 0) in idx

        filter_mask, raw = variable.id.read_direct_chunk((0, 0, 0, 0))
        assert filter_mask == 0
        assert len(raw) == info0.size


def test_unpacked_chunk_index_can_back_a_kerchunk_like_reconstruction():
    path = Path(__file__).resolve().parents[1] / "data" / "test2.pp"

    with File(str(path)) as f:
        name = next(
            name
            for name, variable in f.variables.items()
            if variable.attrs.get("CLASS") != b"DIMENSION_SCALE"
        )
        variable = f[name]
        direct = variable[:]
        refs = {
            "/".join(str(x) for x in chunk_offset): {
                "path": str(path),
                "offset": info.byte_offset,
                "size": info.size,
                "chunk_offset": info.chunk_offset,
            }
            for chunk_offset, info in variable.id.index.items()
        }
        dtype = np.dtype(variable.dtype)
        chunk_shape = variable.chunks
        shape = variable.shape

    rebuilt = np.empty(shape, dtype=dtype)
    rebuilt.fill(np.nan)
    raw_file = path.read_bytes()

    for ref in refs.values():
        start = ref["offset"]
        stop = start + ref["size"]
        raw = raw_file[start:stop]
        block = np.frombuffer(raw, dtype=dtype).reshape(chunk_shape)
        selection = tuple(
            slice(offset, min(offset + csize, full), 1)
            for offset, csize, full in zip(
                ref["chunk_offset"], chunk_shape, shape
            )
        )
        rebuilt[selection] = block

    assert np.allclose(rebuilt, direct, rtol=1e-6, atol=1e-6)
