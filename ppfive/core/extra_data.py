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
    reader, extra_data_offset, extra_data_length, word_size, byte_order
):
    """Read extra data into dictionary.

    :Parameters:

        reader: `ByteReader`
            The file reader.

        extra_data_offset: `int`
            The byte address of the start of the extra data in the
            file.

        extra_data_length: `int`
            The length in bytes of the extra data.

        word_size: `int`
            The word size (``4`` or ``8``).

        byte_order: `str`
            The word byte order (``'little'`` or ``'big'``).

    :Returns:

        `dict`

    """
    if not extra_data_length:
        return {}

    raw_extra_data = reader.read_at(extra_data_offset, extra_data_length)
    extra = ExtraDataUnpacker(raw_extra_data, word_size, byte_order)
    return extra.get_data()


class ExtraDataUnpacker:
    """Extra data unpacker."""

    def __init__(self, raw_extra_data, word_size, byte_order):
        """**Initialisation**

        :Parameters:

            raw_extra_data: `bytes`
                The raw bytes of the packed extra data.

            word_size: `int`
                The word size (``4`` or ``8``).

            byte_order: `str`
                The word byte order (``'little'`` or ``'big'``).

        """
        self.raw_data = raw_extra_data
        self.word_size = word_size

        if word_size == 4:
            self.itype = np.int32
            self.ftype = np.float32
        elif word_size == 8:
            self.itype = np.int64
            self.ftype = np.float64

        self.is_swapped = not byte_order == sys.byteorder

    def next_words_as_bytes(self, n):
        """Return words as bytes.

        Returns the next *n* words as raw bytes, and pop them off the
        front `raw_data`.

        :Parameters:

            n: `int`
                 The number of words to return as bytes

        :Returns:

            `bytes`

        """
        word_size = self.word_size
        is_swapped = self.is_swapped
        rdata = self.raw_data
        pos = n * word_size
        rv = b""
        for i in range(n):
            x = rdata[i * word_size : (i + 1) * word_size]
            if is_swapped:
                x = x[::-1]

            rv += x

        assert len(rv) == pos
        self.raw_data = rdata[pos:]
        return rv

    def convert_bytes_to_string(self, raw):
        """Convert bytes to a string.

        :Parameters:

            raw: `bytes`
                The bytes.

        :Returns:

            `str`
                The decoded string.

        """
        word_size = self.word_size
        if self.is_swapped:
            indices = slice(None, None, -1)
        else:
            indices = slice(None)

        raw = "".join(
            [
                raw[pos : pos + word_size][indices].decode("utf-8")
                for pos in range(0, len(raw), word_size)
            ]
        )

        while raw.endswith("\x00"):
            raw = raw[:-1]

        return raw

    def get_data(self):
        """Get the extra data in a dictionary.

        :Returns:

            `dict`
                The extra data.

        """
        d = {}
        while self.raw_data:
            i = np.frombuffer(self.next_words_as_bytes(1), self.itype)[0]
            if i == 0:
                break

            ia, ib = divmod(i, 1000)
            key, etype = _codes[ib]

            rawvals = self.next_words_as_bytes(ia)
            if etype == float:
                vals = np.frombuffer(rawvals, self.ftype)
            elif etype == str:
                vals = np.array([self.convert_bytes_to_string(rawvals)])

            if key not in d:
                d[key] = vals
            else:
                d[key] = np.append(d[key], vals)

        return d
