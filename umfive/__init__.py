from .high_level import File
from .variable import DataVariable, DimensionScale, Variable
from .core import RecordInfo
from .stash import load_stash_table, stash_records, stash_table
from .io import ByteReader, FileObjReader, LocalPosixReader

from importlib.metadata import version, PackageNotFoundError


try:
    __version__ = version("umfive")
except PackageNotFoundError as exc:
    msg = (
        "umfive package not found, please run `pip install -e .` before "
        "importing the package."
    )
    raise PackageNotFoundError(
        msg,
    ) from exc
