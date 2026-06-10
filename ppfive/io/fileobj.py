from __future__ import annotations

from .bytereader import ByteReader
from .mock_filesystem import MockFilesystem


class FileObjReader(ByteReader):
    """ByteReader adapter for seekable/readable file-like objects."""

    def __init__(self, fileobj):
        """TODO."""
        if not hasattr(fileobj, "read") or not callable(fileobj.read):
            raise ValueError("fileobj must provide a callable read method")

        if not hasattr(fileobj, "seek") or not callable(fileobj.seek):
            raise ValueError("fileobj must provide a callable seek method")

        # File-like object
        self.fileobj = fileobj

        # filename
        path = getattr(fileobj, "path", None)
        if path is None:
            path = getattr(fileobj, "name", "<file-like>")

        self.path = path

        # Store the file system
        try:
            self.fs = fileobj.fs
        except AttributeError:
            # Create a mock file system with selected attributes
            self.fs = MockFilesystem(protocol="file")

    def close(self) -> None:
        """TODO."""
        close = getattr(self.fileobj, "close", None)
        if callable(close):
            close()

    def read_at(self, offset: int, nbytes: int) -> bytes:
        """TODO."""
        if offset < 0:
            raise ValueError("offset must be >= 0")

        if nbytes < 0:
            raise ValueError("nbytes must be >= 0")

        self.fileobj.seek(offset)
        return self.fileobj.read(nbytes)
