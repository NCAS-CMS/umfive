from .bytereader import ByteReader
from .fileobj import FileObjReader

# from .fsspec_reader import FsspecReader
from .local import LocalPosixReader

__all__ = ["ByteReader", "LocalPosixReader", "FsspecReader", "FileObjReader"]
