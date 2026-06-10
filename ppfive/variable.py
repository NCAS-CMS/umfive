from __future__ import annotations

from dataclasses import dataclass, field
from math import prod
from typing import Any, Callable

import numpy as np
from pyfive.indexing import OrthogonalIndexer, ZarrArrayStub

from .constants import (
    INDEX_LBPACK,
    _axiscode_to_units,
    _coord_axis,
    _coord_long_name,
    _coord_positive,
    _coord_standard_name,
)
from .core.data import read_record_raw
from .core.interpret import get_extra_data_length
from .core.models import StoreInfo
from .io.chunk_read import ChunkReadMixin


class _PyfiveAttrs(dict):
    """Attribute mapping tuned for cfdm/p5netcdf compatibility.

    Keep normal Python `str` values for direct user access, but expose those
    strings as byte scalars when iterating `.items()` so cfdm's p5netcdf
    adapter formats them as scalar text instead of character arrays.

    """

    @staticmethod
    def _coerce_for_items(value: Any) -> Any:
        if isinstance(value, str):
            return np.bytes_(value)

        return value

    def items(self):
        """A set-like object providing a view on the items."""
        for key, value in super().items():
            yield key, self._coerce_for_items(value)


class AstypeContext:
    """Context manager to cast reads from a variable."""

    def __init__(self, variable: "Variable", dtype: str | np.dtype):
        self._variable = variable
        self._dtype = np.dtype(dtype)

    def __enter__(self):
        """Enter the runtime context."""
        self._variable._astype = self._dtype

    def __exit__(self, _exc_type, _exc, _tb):
        """Exit the runtime context."""
        self._variable._astype = None


class DataVariableID(ChunkReadMixin):
    """Small dataset-id-like object that backs `DataVariable` reads."""

    def __init__(self, variable):
        """**Initialisation**

        :Parameters:

            variable: `DataVariable`
                The parent data variable instance.

        """
        self._variable = variable
        self._index_cache = None
        self._nthindex = None
        self._record_cache = None

    def __chunk_init_check(self):
        """Check the chunks.

        :Returns:

            `bool`
                False if there are no chunks, or the chunks shape is
                undefined. Otherwise True.

        """
        if (
            self._variable.chunk_shape is None
            or not self._variable.chunk_records
        ):
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
                        - get_extra_data_length(
                            rec.int_hdr, self._variable.file.word_size
                        )
                    ),
                )
                index[chunk_offset] = info
                record_cache[chunk_offset] = rec

            self._index_cache = index
            self._nthindex = sorted(index)
            self._record_cache = record_cache

        return True

    def _get_selection_via_chunks(self, args):
        """Use the zarr orthogonal indexer to extract data for a specfic
        selection within the dataset array and in doing so, only load
        the relevant chunks."""
        array = ZarrArrayStub(self.shape, self.chunks)
        indexer = OrthogonalIndexer(args, array)
        out = np.empty(indexer.shape, dtype=self.dtype)

        self._select_chunks(indexer, out)

        return out

    @property
    def shape(self):
        """Shape of the data array.

        :Returns:

            `tuple`

        """
        return self._variable.shape

    @property
    def chunks(self):
        """The chunk shape.

        :Returns:

            `tuple`

        """
        return self._variable.chunk_shape

    @property
    def dtype(self):
        """The format of the elements in the array."""
        if self._variable.dtype is None:
            return

        return np.dtype(self._variable.dtype)

    @property
    def first_chunk(self):
        """The indices of the first chunk.

        :Returns:

            `tuple` of `int`

        """
        if not self.__chunk_init_check():
            return

        return self._nthindex[0]

    @property
    def index(self):
        """The `StoreInfo` object for each chunk.

        :Returns:

            `dict`
                 The `StoreInfo` objects, each keyed by the `tuple` of
                 its chunk indices.

        """
        if not self.__chunk_init_check():
            raise TypeError("Dataset is not chunked ")

        return self._index_cache

    def get_data(self, args=()):
        """Called by `DataVariable.__getitem__`."""
        if self.__chunk_init_check():
            return self._get_selection_via_chunks(args)

        # Fallback for variables with data_loader but no chunk records
        variable = self._variable
        if variable.data_loader is not None:
            data = variable.data_loader(**variable.data_loader_options)
            if data is None:
                return

            return data[args] if args else data

    def iter_chunks(self, args=()):
        """Iterate over chunks in a chunked dataset.

        The args argument is a (possibly empty) sequence of indices that
        defines the region to be used. If an empty sequence then the
        entire dataspace will be used for the iterator.

        For each chunk within the given region, the iterator yields a
        tuple of indices that gives the intersection of the given chunk
        with the selection area. This can be used to read data in that
        chunk.

        """
        shape = self.shape
        if not shape:
            return iter(())

        chunks = self.chunks or shape
        normalized = []
        for axis, size in enumerate(shape):
            if axis < len(args) and isinstance(args[axis], slice):
                start, stop, step = args[axis].indices(size)
                if step != 1:
                    raise NotImplementedError(
                        "iter_chunks only supports step=1 slices"
                    )
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
        """Return total number of chunks in dataset."""
        if self.__chunk_init_check():
            return len(self._index_cache)

        return 0

    def get_chunk_info(self, index):
        """Retrieve storage information about a chunk specified by its
        index."""
        if self.__chunk_init_check():
            return self._index_cache[self._nthindex[index]]

        raise TypeError("Dataset is not chunked ")

    def get_chunk_info_by_coord(self, coordinate_index):
        """Retrieve information about a chunk specified by the array
        address of the chunk's first element in each dimension."""
        if self.__chunk_init_check():
            return self._index_cache[tuple(coordinate_index)]

        raise TypeError("Dataset is not chunked ")

    def read_direct_chunk(self, chunk_position, **kwargs):
        """Returns a tuple containing the filter_mask and the raw data
        storing this chunk as bytes.

        Additional arguments supported by ``h5py`` are not supported here.

        """
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


class _Mixin:
    """Mixin class for dataset variables."""

    def __len__(self):
        """Return len(self)."""
        shape = self.shape
        if not shape:
            raise TypeError(f"len() of unsized object: {self!r}")

        return shape[0]

    def __repr__(self):
        """Return repr(self)."""
        dimensions = self.dimensions
        if dimensions is None:
            dimensions = ""
        else:
            dims = ", ".join(dim for dim in dimensions)
            dimensions = f", dimensions=({dims})"

        return (
            f"<ppfive.{self.__class__.__name__}: "
            f"{self.name}, shape={self.shape}{dimensions}>"
        )

    @property
    def dimensions(self):
        """The dimension names.

        :Returns:

            `tuple` or `None`
                The dimension names, or `None` if they are undefined.

        """
        DIMENSION_LIST = self.attrs.get("DIMENSION_LIST")
        if DIMENSION_LIST is None:
            return

        return tuple(dim[0] for dim in DIMENSION_LIST)

    @property
    def ndim(self):
        """The array's number of dimensions."""
        return len(self.shape)

    @property
    def size(self):
        """Number of elements in the array."""
        return prod(self.shape)

    def _setattrs_from_axiscode(self, axiscode):
        """Set attributes according to a PP axis code.

        :Parameters:

            axiscode: `int` or `None`
                The integer PP axis code, or `None` if there isn't
                one, in which case no attributes are set.

        :Returns:

            `None`

        """
        if axiscode is None:
            return

        name = _coord_standard_name.get(axiscode)
        if name is not None:
            self.setattr("standard_name", name)
            if self.name is None:
                self.name = name
        else:
            name = _coord_long_name.get(axiscode)
            if name is not None:
                self.setattr("long_name", name)

        axis = _coord_axis.get(axiscode)
        if axis is not None:
            self.setattr("axis", axis)

        positive = _coord_positive.get(axiscode)
        if positive is not None:
            self.setattr("positive", positive)

        units = _axiscode_to_units.get(axiscode)
        if units:
            self.setattr("units", units)

    def setattr(self, name, value):
        """Set an attribute.

        :Parameters:

            name: `str`
                The name of the attribute.

            value:
                The attribute value.

        :Returns:

            `None`

        """
        self.attrs[name] = value


class DimensionScale(_Mixin):
    """Internal pyfive-like dimension-scale dataset."""

    def __init__(
        self,
        name=None,
        data=None,
        size=None,
        axiscode=None,
        attrs=None,
        file_obj=None,
        Netcdf4Dimid=None,
    ):
        """**Initialisation**

        :Parameters:

            name: `str` or `None`, optional
                The dimension name.

            data: `np.ndarray` or `None`, optional
                The 1-d data, or `None` if dimension has no data.

            size: `int` or `None`, optional
                The size of the dimension. Ignored if *data* is set to
                an array.

            axiscode: `int` or `None`, optional
                The integer PP axis code from which attributes are
                derived, or `None` if there isn't one.

            attrs: `dict` or `None`, optional
                The dimension coordinate attributes, which override
                any with the same name set via *axiscode*.

            file_obj: `File` or `None, optional
                The parent dataset.

            Netcdf4Dimid: `list` or `None`, optional
                A single-element list containing the next available
                "_NetCDF4Dimid" attribute value. The list is updated
                in-place.

        """
        if data is None:
            self._data = None
            self.shape = (int(size),)
            self.dtype = np.dtype("float32")
        else:
            data = np.asanyarray(data)
            if data.ndim != 1:
                raise ValueError("Dimension scale data must be 1-d")

            self._data = data
            self.shape = data.shape
            self.dtype = data.dtype

        self.maxshape = self.shape

        self.name = name
        self.file = file_obj
        self.chunks = None

        self.attrs = {}
        self._setattrs_from_axiscode(axiscode)
        if attrs:
            self.attrs.update(attrs)

        if Netcdf4Dimid is None:
            Netcdf4Dimid = [np.int32(0)]

        hdf5_attrs = {
            "CLASS": b"DIMENSION_SCALE",
            "_Netcdf4Dimid": Netcdf4Dimid[0],
        }

        # Increment Netcdf4Dimid in-place
        Netcdf4Dimid[0] += 1

        if data is None:
            hdf5_attrs["NAME"] = (
                b"This is a netCDF dimension but not a netCDF variable."
            )
        else:
            hdf5_attrs["NAME"] = b"netCDF dimension coordinate variable"

        self.attrs.update(hdf5_attrs)

    def __getitem__(self, key):
        """Return self[key]."""
        data = self._data
        if data is None:
            raise ValueError(
                "Can't index a DimensionScale that is a netCDF dimension "
                "but not a netCDF variable."
            )

        return data[key]

    def __repr__(self):
        """Return repr(self)."""
        out = f"<ppfive.{self.__class__.__name__}: {self.name}, "
        if self._data is None:
            out += f"size={self.shape[0]}>"
        else:
            out += f"shape={self.shape}>"

        return out

    @property
    def dimensions(self):
        """The dimension name.

        :Returns:

            `tuple` or `None`
                The dimension name, or `None` if it is undefined.

        """
        name = self.name
        if name is None:
            return

        return (name,)


class Variable(_Mixin):
    """A metadata variable in the dataset.

    Any variable that is not a dimension coordinate variable nor a
    data variable is represented by a `Variable` instance. This
    includes coordinate bounds, auxilary coordinate, domain ancillary,
    and grid mapping variables.

    A dimension coordinate variable (with or within an array) is
    represented by a `DimensionScale` instance, and a data variable is
    represented by a `DataVariable` instance.

    """

    def __init__(
        self,
        name: str | None = None,
        data=None,
        axiscode: int | None = None,
        attrs: dict | None = None,
        DIMENSION_LIST: tuple | None = None,
    ):
        """**Initialisation**

        :Parameters:

            name: `str` or `None`, optional
                The variable name.

            data: `np.ndarray` or `None`, optional
                The data.

            axiscode: `int` or `None`, optional
                The integer PP axis code from which attributes are
                derived, or `None` if there isn't one.

            attrs: `dict` or `None`, optional
                The variable attributes, which override any with the
                same name set via *axiscode*.

            DIMENSION_LIST: `tuple` or `None`, optional
                The dimension names for the data, e.g. ``()``,
                ``(('time',),)``, ``(('latitude',), ('longitude',))``

        """
        self.name = name
        self._data = data
        self.shape = data.shape
        self.dtype = data.dtype
        self.maxshape = data.shape
        self.chunks = None

        self.attrs = {}
        self._setattrs_from_axiscode(axiscode)
        if attrs:
            self.attrs.update(attrs)

        if DIMENSION_LIST is None and data is not None and not self.shape:
            DIMENSION_LIST = ()

        if DIMENSION_LIST is None:
            raise ValueError(
                "Must provide DIMENSION_LIST when instantiating a "
                f"non-scalar Variable instance: {name}({self.shape})"
            )

        if len(DIMENSION_LIST) != len(self.shape):
            raise ValueError(
                "DIMENSION_LIST must have the same number of elements as "
                "there are data dimensions"
            )

        self.setattr("DIMENSION_LIST", DIMENSION_LIST)

    def __getitem__(self, key):
        """Return self[key]."""
        return self._data[key]


@dataclass(repr=False)
class DataVariable(_Mixin):
    """Minimal pyfive-like variable for PP/Fields data."""

    name: str
    attrs: dict[str, Any] = field(default_factory=dict)
    shape: tuple[int, ...] = field(default_factory=tuple)
    dtype: Any = None
    chunk_shape: tuple[int, ...] | None = None
    data_loader: Callable[[], Any] | None = None
    data_loader_options: dict | None = None
    file: Any = None
    chunk_records: list[dict[str, Any]] = field(default_factory=list)
    _astype: np.dtype | None = field(default=None, init=False, repr=False)
    id: DataVariableID = field(init=False, repr=False)
    DIMENSION_LIST: tuple[tuple, ...] | None = None

    def __post_init__(self):
        if self.dtype is not None:
            self.dtype = np.dtype(self.dtype)

        if self.data_loader_options is None:
            self.data_loader_options = {}

        self.id = DataVariableID(self)

        self.parent = self.file

        DIMENSION_LIST = self.DIMENSION_LIST
        if DIMENSION_LIST is None and not self.shape:
            DIMENSION_LIST = ()

        if DIMENSION_LIST is None:
            raise ValueError(
                "Must provide DIMENSION_LIST when instantiating a "
                "non-scalar DataVariable instance: "
                f"{self.name}, shape={self.shape}"
            )

        if len(DIMENSION_LIST) != len(self.shape):
            raise ValueError(
                "DIMENSION_LIST must have the same number of elements as "
                "there are data dimensions"
            )

        self.setattr("DIMENSION_LIST", DIMENSION_LIST)

    def __getitem__(self, key):
        """Return self[key]."""
        data = self.id.get_data(key)
        if data is None:
            return

        if self._astype is None:
            return data

        return data.astype(self._astype, copy=False)

    def __array__(self, dtype=None, copy=None):
        """The numpy array interface.

        :Parameters:

            dtype: optional
                Typecode or data-type to which the array is cast.

            copy: `None` or `bool`
                Included to match the `numpy.ndarray.__array__` API,
                but ignored. The returned numpy array is always
                independent.

        :Returns:

            `numpy.ndarray`
                An independent numpy array of the data.

        """
        array = self[...]
        if array is None:
            raise RuntimeError("Failed to get data array")

        if dtype is None:
            return array

        return array.astype(dtype, copy=False)

    @property
    def chunks(self):
        """The chunk shape.

        :Returns:

            `tuple`

        """
        return self.chunk_shape

    @property
    def compression(self):
        """Returns `None`.

        Provided for compatability with the `pyfive` API.

        """
        return

    @property
    def compression_modes(self):
        """The unique data chunk compression flags.

        These are the unique values, excluding ``0``, of the N2 digit
        of LBPACK across all data chunks in the variable.

        1: Data compressed using the N3rd group of compressed ﬁeld
           index arrays in the dump.
        2: Data compressed with the N3rd bit mask

        """
        out = {
            (int(chunk_record["record"].int_hdr[INDEX_LBPACK]) // 10) % 10
            for chunk_record in self.chunk_records
        }

        out.discard(0)
        return sorted(out)

    @property
    def compression_opts(self):
        """Returns `None`.

        Provided for compatability with the `pyfive` API.

        """
        return

    @property
    def dims(self):
        """Returns `None`.

        Provided for compatability with the `pyfive` API.

        """
        return

    @property
    def fillvalue(self):
        """Fillvalue of the data."""
        return self.attrs.get("missing_value")

    @property
    def fletcher32(self):
        """Boolean indicator if fletcher32 filter was applied.

        Provided for compatability with the `pyfive` API.

        """
        return

    @property
    def has_extra_data(self):
        """Whether there is any extra data.

        :Returns:

            `bool`

        """
        chunk_records = self.chunk_records
        if not chunk_records:
            return False

        return bool(chunk_records[0]["record"].extra_data)

    @property
    def lbpack(self):
        """The unique data chunk LBPACK values.

        These are the unique values of the LBPACK across all data chunks
        in the variable.

        """
        return sorted(
            {
                int(chunk_record["record"].int_hdr[INDEX_LBPACK])
                for chunk_record in self.chunk_records
            }
        )

    @property
    def maxshape(self):
        """Maximum shape of the data."""
        return self.shape

    @property
    def packing_modes(self):
        """The unique data chunk packing flags.

        These are the unique values, excluding ``0``, of the N1 digit
        of LBPACK across all data chunks in the variable.

        1: Data packed using WGDOS archive method.
        2: Data packed using CRAY 32 bit method.
        3: Data compressed using the GRIB method.
        4: Data compressed using Run Length Encoding

        """
        out = {
            int(chunk_record["record"].int_hdr[INDEX_LBPACK]) % 10
            for chunk_record in self.chunk_records
        }

        out.discard(0)
        return sorted(out)

    @property
    def scaleoffset(self):
        """Returns `None`.

        Provided for compatability with the `pyfive` API.

        """
        return

    @property
    def shuffle(self):
        """Boolean indicator if shuffle filter was applied.

        Provided for compatability with the `pyfive` API.

        """
        return False

    def astype(self, dtype: str | np.dtype) -> AstypeContext:
        """Return a context manager which returns data as a particular
        type.

        Conversion is handled by NumPy after reading extracting the
        data.

        """
        return AstypeContext(self, dtype)

    def get_parallelism(self):
        """Configure data chunk read parallelism configuration.

        .. seealso:: `set_parallelism`

        :Returns:

            `dict`
                The the "thread_count" and "cat_range_allowed"
                parameters to be used when accessing the data. See
                `set_parallelism` for details.

        """
        return self.data_loader_options.copy()

    def iter_chunks(self, args=()):
        """Iterate over data chunks.

        The *args* argument is a (possibly empty) sequence of indices
        that defines the region to be used. If an empty sequence then
        the entire dataspace will be used for the iterator.

        For each chunk within the given region, the iterator yields a
        tuple of indices that gives the intersection of the given chunk
        with the selection area. This can be used to read data in that
        chunk.

        """
        return self.id.iter_chunks(args)

    def read_direct(
        self, array: np.ndarray, source_sel=None, dest_sel=None
    ) -> None:
        """Read from the dataset directly into a `numpy` array.

        This is equivalent to dset[source_sel] = arr[dset_sel].

        Creation of intermediates is not avoided. This method if
        provided from compatibility with pyfive, it is not efficient.

        """
        if source_sel is None:
            source_sel = slice(None)

        if dest_sel is None:
            dest_sel = slice(None)

        array[dest_sel] = self[source_sel]

    def set_parallelism(self, max_thread_count=0, cat_range_allowed=True):
        """Configure data chunk read parallelism.

        .. seealso:: `get_parallelism`

        :Parameters:

            max_thread_count: `int`, optional
                The maximum number of concurrent worker threads to use
                for reading the local POSIX data chunks of the
                variable. Ignored for non-local POSIX readers. If
                ``0`` (the default) then the reading of data chunks
                runs sequentially in the main thread. The number of
                threads is limited by the number of data
                chunks.

            cat_range_allowed: `bool`, optional
                If True (the default), uses fsspec's bulk range
                fetching to download multiple data chunks concurrently
                in a single network request. Ignored for non-fsspec
                reader. Set to False to force sequential chunk
                loading. Defaults to True.

        :Returns:

            `None`

        """
        thread_count = min(len(self.chunk_records), int(max_thread_count))
        self.data_loader_options.update(
            {
                "thread_count": thread_count,
                "cat_range_allowed": bool(cat_range_allowed),
            }
        )
