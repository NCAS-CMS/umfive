import sys

import numpy as np

_codes = {
    1: ("x", float),
    2: ("y", float),
    3: ("y_domain_lower_bound", float),
    4: ("x_domain_lower_bound", float),
    5: ("y_domain_upper_bound", float),
    6: ("x_domain_upper_bound", float),
    7: ("z_domain_lower_bound", float),
    8: ("z_domain_upper_bound", float),
    10: ("title", str),
    11: ("domain_title", str),
    12: ("x_lower_bound", float),
    13: ("x_upper_bound", float),
    14: ("y_lower_bound", float),
    15: ("y_upper_bound", float),
}


def read_extra_data(
    reader, extra_data_offset, extra_data_length, word_size, byte_ordering
):
    """TODO."""
    if not extra_data_length:
        return {}

    raw_extra_data = reader.read_at(extra_data_offset, extra_data_length)
    extra = ExtraDataUnpacker(raw_extra_data, word_size, byte_ordering)
    return extra.get_data()


class ExtraDataUnpacker:
    """TODO."""

    _int_types = {4: np.int32, 8: np.int64}
    _float_types = {4: np.float32, 8: np.float64}

    def __init__(self, raw_extra_data, word_size, byte_ordering):
        """TODO."""
        self.rdata = raw_extra_data
        self.ws = word_size
        self.itype = self._int_types[word_size]
        self.ftype = self._float_types[word_size]
        # byte_ordering is 'little_endian' or 'big_endian'
        # sys.byteorder is 'little' or 'big'
        self.is_swapped = not byte_ordering.startswith(sys.byteorder)

    def next_words(self, n):
        """Return words as bytes.

        Return next n words as raw data string, and pop them off the
        front of the string.

        """
        ws = self.ws
        is_swapped = self.is_swapped
        rdata = self.rdata
        pos = n * ws
        rv = b""
        for i in range(n):
            x = rdata[i * ws : (i + 1) * ws]
            if is_swapped:
                x = x[::-1]

            rv += x

        assert len(rv) == pos
        self.rdata = rdata[pos:]
        return rv

    def convert_bytes_to_string(self, st):
        """Convert bytes to string.

        :Returns:

            `str`

        """
        ws = self.ws
        if self.is_swapped:
            indices = slice(None, None, -1)
        else:
            indices = slice(None)

        st = "".join(
            [
                st[pos : pos + ws][indices].decode("utf-8")
                for pos in range(0, len(st), ws)
            ]
        )

        while st.endswith("\x00"):
            st = st[:-1]

        return st

    def get_data(self):
        """Get the (key, value) pairs for extra data.

        :Returns:

            `ExtraData`

        """
        d = {}
        while self.rdata:
            i = np.frombuffer(self.next_words(1), self.itype)[0]
            if i == 0:
                break

            ia, ib = divmod(i, 1000)
            key, etype = _codes[ib]

            rawvals = self.next_words(ia)
            if etype == float:
                vals = np.frombuffer(rawvals, self.ftype)
            elif etype == str:
                vals = np.array([self.convert_bytes_to_string(rawvals)])

            if key not in d:
                d[key] = vals
            else:
                d[key] = np.append(d[key], vals)

        return d
