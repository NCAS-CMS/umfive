from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
from pyfive.indexing import OrthogonalIndexer, ZarrArrayStub, replace_ellipsis

from .core.data import read_record_raw
from .core.interpret import get_extra_data_length
from .core.models import StoreInfo
from .io.chunk_read import ChunkReadMixin
from .lookup_header import CF_CONVENTIONS

class AstypeContext:
    """Context manager to cast reads from a variable."""

    def __init__(self, variable: "Variable", dtype: str | np.dtype):
        self._variable = variable
        self._dtype = np.dtype(dtype)

    def __enter__(self):
        self._variable._astype = self._dtype

    def __exit__(self, exc_type, exc, tb):
        self._variable._astype = None


class DataVariableID(ChunkReadMixin):
    """Small dataset-id-like object that backs DataVariable reads."""

    def __init__(self, variable: "DataVariable"):
        self._variable = variable
        self._index_cache = None
        self._nthindex = None
        self._record_cache = None

    @property
    def shape(self):
        return self._variable.shape

    @property
    def dtype(self):
        return np.dtype(self._variable.dtype) if self._variable.dtype is not None else None

    @property
    def chunks(self):
        return self._variable.chunk_shape

    @property
    def first_chunk(self):
        if not self.__chunk_init_check():
            return None
        return self._nthindex[0]

    @property
    def index(self):
        if not self.__chunk_init_check():
            raise TypeError("Dataset is not chunked ")
        return self._index_cache

    def __chunk_init_check(self):
        if self._variable.chunk_shape is None or not self._variable.chunk_records:
            return False

        if self._index_cache is None:
            index = {}
            record_cache = {}
            for item in self._variable.chunk_records:
                rec = item["record"]
                chunk_offset = tuple(int(x) for x in item["chunk_coords"])
                info = StoreInfo(
                    chunk_offset=chunk_offset,
                    filter_mask=0,
                    byte_offset=int(rec.data_offset),
                    size=int(
                        rec.disk_length
                        - get_extra_data_length(rec.int_hdr, self._variable.file.word_size)
                    ),
                )
                index[chunk_offset] = info
                record_cache[chunk_offset] = rec
            self._index_cache = index
            self._nthindex = sorted(index)
            self._record_cache = record_cache

        return True

    def _get_selection_via_chunks(self, args):
        array = ZarrArrayStub(self.shape, self.chunks)
        indexer = OrthogonalIndexer(args, array)
        out = np.empty(indexer.shape, dtype=self.dtype)

        self._select_chunks(indexer, out)

        return out

    def get_data(self, args=(), fillvalue=None):
        del fillvalue

        if self.__chunk_init_check():
            return self._get_selection_via_chunks(args)

        # Fallback for variables with data_loader but no chunk records
        if self._variable.data_loader is not None:
            data = self._variable.data_loader()
            if data is None:
                return None
            return data[args] if args else data

        return None

    def iter_chunks(self, sel=()):
        shape = self.shape
        if not shape:
            return iter(())

        chunks = self.chunks or shape
        normalized = []
        for axis, size in enumerate(shape):
            if axis < len(sel) and isinstance(sel[axis], slice):
                start, stop, step = sel[axis].indices(size)
                if step != 1:
                    raise NotImplementedError("iter_chunks only supports step=1 slices")
            else:
                start, stop = 0, size
            normalized.append((start, stop, chunks[axis]))

        chunk_slices = []
        for start, stop, chunk in normalized:
            axis_slices = []
            pos = start
            while pos < stop:
                axis_slices.append(slice(pos, min(pos + chunk, stop), 1))
                pos += chunk
            chunk_slices.append(axis_slices)

        def _generator(axis=0, prefix=()):
            if axis == len(chunk_slices):
                yield prefix
                return
            for item in chunk_slices[axis]:
                yield from _generator(axis + 1, prefix + (item,))

        return _generator()

    def get_num_chunks(self):
        if self.__chunk_init_check():
            return len(self._index_cache)
        return 0

    def get_chunk_info(self, index):
        if self.__chunk_init_check():
            return self._index_cache[self._nthindex[index]]
        raise TypeError("Dataset is not chunked ")

    def get_chunk_info_by_coord(self, coordinate_index):
        if self.__chunk_init_check():
            return self._index_cache[tuple(coordinate_index)]
        raise TypeError("Dataset is not chunked ")

    def get_chunk_info_from_chunk_coord(self, coordinate_index):
        return self.get_chunk_info_by_coord(coordinate_index)

    def read_direct_chunk(self, chunk_position, **kwargs):
        del kwargs
        if not self.__chunk_init_check():
            raise TypeError("Dataset is not chunked ")
        chunk_position = tuple(chunk_position)
        if chunk_position not in self._index_cache:
            raise OSError("Chunk coordinates must lie on chunk boundaries")

        rec = None
        for item in self._variable.chunk_records:
            if tuple(item["chunk_coords"]) == chunk_position:
                rec = item["record"]
                break

        if rec is None:
            raise OSError("Chunk coordinates must lie on chunk boundaries")

        raw = read_record_raw(
            self._variable.file._reader,
            rec,
            self._variable.file.word_size,
        )
        return 0, raw


@dataclass
class DataVariable:
    """Minimal pyfive-like variable surface for PP/Fields data."""

    name: str
    attrs: dict[str, Any] = field(default_factory=dict)
    shape: tuple[int, ...] = field(default_factory=tuple)
    dtype: Any = None
    chunk_shape: tuple[int, ...] | None = None
    data_loader: Callable[[], Any] | None = None
    file: Any = None
    parent: Any = None
    chunk_records: list[dict[str, Any]] = field(default_factory=list)
    _astype: np.dtype | None = field(default=None, init=False, repr=False)
    id: DataVariableID = field(init=False, repr=False)

    def __post_init__(self):
        if self.dtype is not None:
            self.dtype = np.dtype(self.dtype)
        self.id = DataVariableID(self)
        if self.parent is None:
            self.parent = self.file

    def __repr__(self):
        dimensions = self.dimensions
        if dimensions is None:
            dimensions = ""
        else:
            dims = ', '.join(dim for dim in dimensions)
            dimensions = f", dimensions=({dims})"
                       
        return (
            f"<ppfive.{self.__class__.__name__}: "
            f"{self.name}, shape={self.shape}{dimensions}>"
        )

    @property
    def ndim(self) -> int:
        return len(self.shape)

    @property
    def size(self) -> int:
        if not self.shape:
            return 0
        return int(np.prod(self.shape))

    @property
    def value(self):
        return self[()]

    @property
    def dimensions(self):
        DIMENSION_LIST = self.attrs.get('DIMENSION_LIST')
        if DIMENSION_LIST is None:
            return None

        return tuple(dim[0] for dim in DIMENSION_LIST)
        
    def __getitem__(self, key):
        data = self.id.get_data(key, self.fillvalue)
        if data is None:
            return None
        if self._astype is None:
            return data
        return np.asarray(data).astype(self._astype)

    def __array__(self):
        data = self.id.get_data(())
        if data is None:
            raise TypeError("DataVariable has no data loader configured")
        return np.asarray(data)

    def __len__(self):
        return self.shape[0]

    def len(self):
        return len(self)

    def read_direct(self, array: np.ndarray, source_sel=None, dest_sel=None) -> None:
        if source_sel is None:
            source_sel = slice(None)
        if dest_sel is None:
            dest_sel = slice(None)
        array[dest_sel] = self[source_sel]

    def astype(self, dtype: str | np.dtype) -> AstypeContext:
        return AstypeContext(self, dtype)

    def iter_chunks(self, sel=()):
        return self.id.iter_chunks(sel)

    def to_reference_dict(self) -> dict[str, Any]:
        refs: dict[str, Any] = {}
        for chunk_coords, info in self.id.index.items():
            rec = None
            for item in self.chunk_records:
                if tuple(item["chunk_coords"]) == tuple(chunk_coords):
                    rec = item["record"]
                    break

            if rec is None:
                continue

            key = ".".join(str(x) for x in chunk_coords)
            refs[key] = {
                "path": getattr(self.file, "filename", None),
                "chunk_coords": list(info.chunk_offset),
                "header_offset": rec.header_offset,
                "data_offset": info.byte_offset,
                "disk_length": info.size,
                "filter_mask": info.filter_mask,
                "int_hdr": rec.int_hdr.tolist(),
                "real_hdr": rec.real_hdr.tolist(),
            }

        return {
            "version": 1,
            "name": self.name,
            "path": getattr(self.file, "filename", None),
            "shape": list(self.shape),
            "dtype": np.dtype(self.dtype).str if self.dtype is not None else None,
            "chunk_shape": list(self.chunk_shape) if self.chunk_shape is not None else None,
            "word_size": getattr(self.file, "word_size", None),
            "byte_ordering": getattr(self.file, "byte_ordering", None),
            "refs": refs,
        }

    # Dataset-like attributes that are not currently meaningful for PP/Fields.
    @property
    def chunks(self):
        return self.chunk_shape

    @property
    def compression(self):
        return None

    @property
    def compression_opts(self):
        return None

    @property
    def shuffle(self):
        return None

    @property
    def fletcher32(self):
        return None

    @property
    def maxshape(self):
        return None

    @property
    def fillvalue(self):
        return None

    @property
    def dims(self):
        return None

    @property
    def scaleoffset(self):
        return None

    @property
    def external(self):
        return None

    @property
    def is_virtual(self):
        return None
