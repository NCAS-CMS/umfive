from .dataset import File, DimensionScale, Variable
from .variable import DataVariable
from .stash import load_stash_table, stash_records, stash_table

try:
    import pyfive
except Exception:  # pragma: no cover - optional dependency
    pyfive = None

if pyfive is not None:
    # Let external callers (e.g. cfdm/cf-python dispatch) treat ppfive
    # files as pyfive-like file handles.
    pyfive.File.register(File)
    pyfive.Dataset.register(DataVariable)
    pyfive.Dataset.register(DimensionScale)
    pyfive.Dataset.register(Variable)
