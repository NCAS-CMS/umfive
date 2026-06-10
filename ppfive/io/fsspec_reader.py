#from __future__ import annotations
#
#from .base import ByteReader
#
#
#class FsspecReader(ByteReader):
#    """Fsspec-backed byte reader with absolute reads."""
#
#    def __init__(self, filesystem, path: str):
#        """TODO."""
#        self.path = path
#        self._fh = filesystem.open(self.path, "rb")
#        self.fs = self._fh.fs
#
#    def read_at(self, offset: int, nbytes: int) -> bytes:
#        """TODO."""
#        if offset < 0:
#            raise ValueError("offset must be >= 0")
#
#        if nbytes < 0:
#            raise ValueError("nbytes must be >= 0")
#
#        self._fh.seek(offset)
#        return self._fh.read(nbytes)
#
#    def close(self) -> None:
#        """TODO."""
#        if self._fh is not None:
#            self._fh.close()
#            self._fh = None
#
#    def __enter__(self) -> "FsspecReader":
#        """Enter the runtime context."""
#        return self
#
#    def __exit__(self, exc_type, exc, tb) -> None:
#        """Exit the runtime context."""
#        self.close()
