from __future__ import annotations

from abc import ABC, abstractmethod


class ByteReader(ABC):
    """Minimal transport boundary for random-access reads."""

    def __enter__(self) -> "FsspecReader":
        """Enter the runtime context."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Exit the runtime context."""
        self.close()

    @abstractmethod
    def read_at(self, offset: int, nbytes: int) -> bytes:
        """Read ``nbytes`` from absolute byte ``offset``."""

    def close(self) -> None:
        """Close underlying resources if needed."""
