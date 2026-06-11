from __future__ import annotations

try:
    from . import _wgdos
except ImportError:  # pragma: no cover
    _wgdos = None


def unpack_wgdos(data, nout, mdi, word_size):
    """Unpack WGDOS packed data.

    :Parameters:

        data: `bytes`
            The raw bytes of the packed data.

        nout: `int`
            The size of the unpacked data in words.

        mdi: `float`
            The missing data value.

        word_size: `int`
            The word size (``4`` or ``8``).

    :Returns:

        `np.ndarray`
            The unpacked data in a 1-d array.

    """
    if _wgdos is None:
        raise NotImplementedError("WGDOS extension is not available")

    return _wgdos.unwgdos(data, nout, mdi, word_size)
