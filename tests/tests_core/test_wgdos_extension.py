from umfive import File, wgdos


def test_wgdos_extension_importable():
    assert wgdos._wgdos is not None
    assert hasattr(wgdos._wgdos, "unwgdos")


def test_wgdos_read():
    f = File("tests/data/wgdos_packed.pp")
    data = f[f.data_variables[0]][...]
    assert data.shape == (1, 1, 145, 192)
    assert data.item(0) == -3.078369140625
    assert data.item(-1) == -9.35107421875
    assert data.mean() == 3.808042
