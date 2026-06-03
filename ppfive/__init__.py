from .file import File, _DimensionScale, _Variable
from .variable import DataVariable

try:
    import pyfive
except Exception:  # pragma: no cover - optional dependency
    pyfive = None

if pyfive is not None:
    # Let external callers (e.g. cfdm/cf-python dispatch) treat ppfive
    # files as pyfive-like file handles.
    pyfive.File.register(File)
    pyfive.Dataset.register(DataVariable)
    pyfive.Dataset.register(_DimensionScale)
    pyfive.Dataset.register(_Variable)

__all__ = ["File", "Variable"]
