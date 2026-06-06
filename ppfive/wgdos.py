from __future__ import annotations

import numpy as np

try:
    from . import _wgdos
except (
    ImportError
):  # pragma: no cover - exercised when extension is unavailable
    _wgdos = None


def unpack_wgdos(
    data: bytes, nout: int, mdi: float, word_size: int
) -> np.ndarray:
    if _wgdos is None:
        raise NotImplementedError("WGDOS extension is not available")

    return _wgdos.unwgdos(data, nout, mdi, word_size)
