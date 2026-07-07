from __future__ import annotations

from abc import ABC, abstractmethod


class ByteReader(ABC):
    """Minimal transport boundary for random-access reads."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    @abstractmethod
    def read_at(self, offset, nbytes):
        """Read ``nbytes`` from absolute byte ``offset``.

        :Parameters:

            offset: `int`
                Start reading at this byte address.

            nbytes: `int`
                Read this many bytes.

        :Returns:

            `bytes`
                The read bytes.

        """

    def close(self) -> None:
        """Close underlying resources if needed.

        :Returns:

            `None`

        """
