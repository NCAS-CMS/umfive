from .bytereader import ByteReader
from .fileobj import FileObjReader

# from .fsspec_reader import FsspecReader
from .local_posix_reader import LocalPosixReader

__all__ = ["ByteReader", "LocalPosixReader", "FileObjReader"]
