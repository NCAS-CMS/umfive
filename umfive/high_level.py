import logging
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from .constants import (
    ATOL,
    CF_CONVENTIONS,
    INDEX_BDATUM,
    INDEX_BDX,
    INDEX_BDY,
    INDEX_BGOR,
    INDEX_BHLEV,
    INDEX_BHRLEV,
    INDEX_BLEV,
    INDEX_BMDI,
    INDEX_BMKS,
    INDEX_BPLAT,
    INDEX_BPLON,
    INDEX_BRLEV,
    INDEX_BRSVD1,
    INDEX_BRSVD2,
    INDEX_BZX,
    INDEX_BZY,
    INDEX_LBCODE,
    INDEX_LBEXP,
    INDEX_LBFC,
    INDEX_LBHEM,
    INDEX_LBLEV,
    INDEX_LBMIN,
    INDEX_LBMIND,
    INDEX_LBNPT,
    INDEX_LBPACK,
    INDEX_LBPROC,
    INDEX_LBROW,
    INDEX_LBSRCE,
    INDEX_LBTIM,
    INDEX_LBUSER1,
    INDEX_LBUSER3,
    INDEX_LBUSER4,
    INDEX_LBUSER5,
    INDEX_LBUSER7,
    INDEX_LBVC,
    INDEX_LBYR,
    INDEX_LBYRD,
    PP_RMDI,
    PSTAR,
    RTOL,
    BMDI_no_missing_data_value,
    _coord_long_name,
    _coord_positive,
    _lbsrce_model_codes,
    _lbvc_to_axiscode,
    _n_runid_characters,
    _runid_characters,
)
from .core import detect_file_type, scan_ff_headers, scan_pp_headers
from .core.variables import build_data_variable_index
from .io import ByteReader, FileObjReader, LocalPosixReader
from .stash import stash_records
from .variable import DataVariable, DimensionScale, Variable

logger = logging.getLogger(__name__)

# Global cache of runids
_cache_runid = {}

# Global cache of days since a reference-time
_cache_date2num = {}


class File(Mapping):
    """Read a PP file or UM fields file.

    32-bit and 64-bit PP and UM fields files of any endian-ness can be
    read.

    2-d "slices" within a single file are always combined, where
    possible, into fields with 3-d or 4-d data.

    **CF mappings**

    The contents of the dataset are mapped to CF dimensions and
    coordinate variables (both as `DimensionScale` objects); auxiliary
    coordinate variables and domain ancillary variables (both as
    `Variable` objects); and data variables (as `DataVariable`
    objects).

    The following CF attributes are derived from the lookup headers
    and, where possible and appropriate, are added to the output
    variables or as global attributes:

    =================  =======================================
    CF attribute       CF variable/global usage
    =================  =======================================
    ``_FillValue``     Data
    ``axis``           Coordinate, Auxiliary coordinate
    ``bounds``         Coordinate, Domain ancillary
    ``calendar``       Coordinate
    ``climatology``    Coordinate
    ``Conventions``    Global
    ``coordinates``    Data
    ``cell_methods``   Data
    ``formula_terms``  Coordinate
    ``grid_mapping``   Data
    ``long_name``      Data, Coordinate, Auxiliary coordinate,
                       Domain ancillary
    ``missing_value``  Data
    ``positive``       Coordinate, Auxiliary coordinate
    ``source``         Data
    ``standard_name``  Data, Coordinate, Auxiliary coordinate,
                       Domain ancillary
    ``units``          Data, Coordinate, Auxiliary coordinate,
                       Domain ancillary
    =================  =======================================

    **Performance**

    The read is lazy in that only the metadata (i.e. the lookup
    headers and any extra data) are accessed during the initial
    read. A data array in the file is then accessed on demand, and
    then only for the part of the data array requested by the
    indexing. Data reads are parallelised over the 2-d slices stored
    for each lookup header (see `get_parallelism` and
    `set_parallelism` methods).

    **Interoperability**

    This class is registered as a virtual subclass of `pyfive.File`,
    meaning that it implements the core abstract methods required to
    safely mimic a native `pyfive.File` layout. Therefore runtime
    type-checking using ``isinstance(file_instance, pyfive.File)``
    will evaluate to `True`.

    **Initialisation**

    :Parameters:

        filename:
            The definition of the PP or UM dataset to be read.  Must
            either be string-like (such as `str` or `pathlib.Path`) or
            file-like (such as `io.BufferedReader`, the result of an
            `fsspec` file system open, or a subclass of
            `umfive.ByteReader`).

        mode: `str`
            The data access mode. Only ``'r'`` (read-only) is allowed.

        um_version: `str` or `None`, optional
            The UM version to be used when decoding the header. Valid
            versions are, for example, ``'4.2'``, ``'6.6.3'`` and
            ``'8.2'``. If the UM version can be derived fron LBSRCE in
            the lookup headers (which is usually the case for files
            created by the UM at versions 5.3 and later) then
            *um_version* parameter is ignored.

            If the UM version can't be derived fron the lookup headers
            (which is usually the case for files created by the UM at
            versions ealier than 5.3) then the given UM version is
            used, and if *um_version* is `None` the UM version 4.5 is
            assumed.

            When the UM version has a third element (such as the 3 in
            6.6.3), this is a special case for which the UM veriosn
            must be provided with the *um_version* parameter, and any
            UM version encoded in the lookup header is ignored.

        height_at_top_of_model: `float` or `None`, optional
            The height in metres of the upper bound of the top model
            level. If `None` (the default) the height at top model is
            taken from the top level's upper bound defined by BRSVD1
            in the lookup headers. If the height can't be determined
            from the header, or the given height is less than or equal
            to 0, then a coordinate reference system will still be
            created that contains the 'a' and 'b' formula term values,
            but without an atmosphere hybrid height dimension
            coordinate construct.

            .. note:: A current limitation is that if pseudolevels and
                      atmosphere hybrid height coordinates are defined
                      by same the lookup headers then the height
                      **can't be determined automatically**. In this
                      case the height may be found after reading as
                      the maximum value of the bounds of the domain
                      ancillary construct containing the 'a' formula
                      term. The file can then be re-read with this
                      height as the *height_at_top_of_model*
                      parameter.

        local_os_cache: `bool`, optional
             If True (the default) then use the local operating system
             cache for local POSIX dataset access when *filename* is a
             string-like. If False then this caching is disabled in
             this case.

        verbose: `int`, optional
             Set the verbosity. If *verbose* is ``0`` there is no
             verbose output, and more output is produced for
             progressively larger values of *verbose*. Values of ``5``
             and higher (or the value ``-1``) produce the same
             maximally verbose output.

        _data_variable_index: `list` or `None`, optional
             The dictionary representations of the data variables. By
             default this is derived internally from *fileaname*, so
             when *_data_variable_index* is provided, *filename* must
             be `None`. See the `__init__` code for details.

    """

    def __init__(
        self,
        filename,
        mode="r",
        um_version=None,
        height_at_top_of_model=None,
        local_os_cache=True,
        verbose=0,
        *,
        _data_variable_index=None,
    ):
        if mode != "r":
            raise ValueError(
                f"{self.__class__.__name__} currently supports "
                "read-only mode='r'"
            )

        if isinstance(filename, ByteReader):
            self._reader = filename
            self._owns_reader = False
            filename = getattr(self._reader, "path", "<byte-reader>")
        elif hasattr(filename, "read") and hasattr(filename, "seek"):
            self._reader = FileObjReader(filename)
            self._owns_reader = False
            filename = getattr(self._reader, "path", None)
            if filename is None:
                filename = getattr(self._reader, "name", "<file-like>")
        elif filename is None:
            if _data_variable_index is None:
                raise ValueError(
                    "_data_variable_index must not be None when "
                    "filename is None"
                )

            self._reader = "no reader: using external _data_variable_index"
        else:
            if _data_variable_index is not None:
                raise ValueError(
                    "_data_variable_index must be None when "
                    "filename is not None"
                )

            if not isinstance(filename, (str, Path)):
                raise ValueError(
                    f"Invalid type of filename argument: {filename!r} of type "
                    f"{type(filename)}. Expected string-like or file-like."
                )

            # Initialise the reader to None - in this case it'll get
            # set to an actual reader later.
            self._reader = None

        if filename is not None:
            self.filename = str(Path(filename))

        self.local_os_cache = bool(local_os_cache)
        if self._reader is None:
            self._reader = LocalPosixReader(
                self.filename,
                local_os_cache=self.local_os_cache,
            )
            self._owns_reader = True

        # Set the default thread_count and cat_range_allowed, and see
        # if we can find the file system protocol.
        thread_count = 0
        try:
            protocol = self._reader.fs.protocol
        except AttributeError:
            pass
        else:
            if isinstance(protocol, tuple):
                protocol = protocol[0]

            if protocol in ("file", "local", "", None):
                # Local file
                protocol = "file"
                cat_range_allowed = False
            else:
                # Remote file
                thread_count = 4
                cat_range_allowed = True

            self.protocol = protocol

        self._fh = self._reader
        self.mode = mode
        self.parent = None
        self.name = "/"
        self.path = "/"
        self.attrs = {"Conventions": CF_CONVENTIONS}
        self.groups = {}
        self.dimensions = {}

        # UM configuration
        if um_version is None:
            # None -> 405
            um_version = 405
        else:
            # '4.5' -> 405
            # '6.6.3' -> 606.3
            um_version = str(um_version).replace(".", "0", 1)
            if "." in um_version:
                um_version = float(um_version)
            else:
                um_version = int(um_version)

        self._um_version = um_version
        self._height_at_top_of_model = height_at_top_of_model

        # Create the variable index
        if _data_variable_index is None:
            file_type = detect_file_type(self._reader)
            self.fmt = file_type.fmt
            self.byte_order = file_type.byte_order
            self.word_size = file_type.word_size
            if file_type.fmt == "PP":
                records = scan_pp_headers(self._reader, file_type)
            else:
                records = scan_ff_headers(self._reader, file_type)

            if not records:
                raise ValueError(
                    f"No valid records found in {self.fmt} file "
                    f"{self.filename}. "
                    f"The file may be corrupted or empty."
                )

            parallelism = {
                "thread_count": thread_count,
                "cat_range_allowed": cat_range_allowed,
            }
            _data_variable_index = build_data_variable_index(
                records,
                self._reader,
                parallelism=parallelism,
            )
        else:
            self.fmt = None
            self.byte_order = None
            self.word_size = None

        # Initialise the dictionary of all (i.e. data and metadata)
        # variables, keyed by their variable names.
        all_variables = {}

        # Initialise the list of data variable names
        data_variables = []

        # Create the cache of metadata `Variable` and `DimensionScale`
        # instance names for the entire dataset. The dictionary keys
        # must be tuples, have akey description as their first
        # element, and are typically derived from lookup header
        # values.
        #
        # E.g.
        #
        # {('grid_mapping',
        #   np.float32(38.0), np.float32(190.0)): 'rotated_latitude_longitude',
        #  ('time_coordinate',
        #   'days since 1979-1-1', 'gregorian', np.int32(121),
        #   (np.int64(120), np.int64(121), np.int64(122)),
        #   (np.int64(121), np.int64(122), np.int64(123))): 'time',
        #  ('time_coordinate',
        #   'days since 1979-1-1', 'gregorian', np.int32(121),
        #   (np.int64(123), np.int64(124), np.int64(125)),
        #   (np.int64(124), np.int64(125), np.int64(126))): 'time_1',
        #  ('x_coordinate',
        #   np.int32(101), np.int32(3), np.int32(106),
        #   np.float32(38.0), np.float32(190.0), np.float32(0.0),
        #   np.float32(339.02), np.float32(0.44)): 'grid_longitude',
        #  ('y_coordinate',
        #   np.int32(101), np.int32(3), np.int32(110),
        #   np.float32(38.0), np.float32(190.0), np.float32(0.0),
        #   np.float32(23.76), np.float32(-0.44)): 'grid_latitude',
        #  ('z_coordinate',
        #   np.int32(8),
        #   (np.float32(850.00006), np.float32(700.00006),
        #    np.float32(500.00003), np.float32(250.00002),
        #    np.float32(50.000004)),
        #   (np.float32(0.0), np.float32(0.0), np.float32(0.0),
        #    np.float32(0.0), np.float32(0.0)),
        #   (np.float32(0.0), np.float32(0.0), np.float32(0.0),
        #    np.float32(0.0), np.float32(0.0))): 'air_pressure'}
        cache = {}

        # Initialise the _Netcdf4Dimid attribute of DimensionScale
        # instances. This list get updated in-place during each
        # DimensionScale initialisation.
        Netcdf4Dimid = [np.int32(0)]

        # Populate the 'all_variables' dictionary
        for meta in _data_variable_index:
            # Add any new metadata variable entries required by this
            # data variable
            data_variable = DataVariableMetadata(
                meta, all_variables, self, cache, Netcdf4Dimid
            )

            name = data_variable.name
            if name is None:
                continue

            DIMENSION_LIST = data_variable.DIMENSION_LIST
            attrs = data_variable.attrs

            # Add a new entry for this data variable
            all_variables[name] = DataVariable(
                name=name,
                attrs=attrs,
                shape=tuple(meta.get("shape", ())),
                dtype=meta.get("dtype"),
                chunk_shape=meta.get("chunk_shape"),
                data_loader=meta.get("data_loader"),
                data_loader_options=meta.get("data_loader_options"),
                file=self,
                chunk_records=tuple(meta.get("chunk_records", ())),
                DIMENSION_LIST=DIMENSION_LIST,
            )
            data_variables.append(name)

        # Try to add an "orog" formula term to vertical
        # coordinates. We have to do this after all of the variables
        # have been created.
        for key, name in cache.items():
            if key[0] != "orography_variables":
                # This key does not store orography variable names
                continue

            if len(name) != 1:
                # There is not exactly one orography variable for this
                # Y-X grid
                continue

            orog_name = name[0]
            yx_grid = key[1]

            # Add the "orog" formula term to all vertical coordinates
            # that share the same Y-X grid as this orography
            for z in cache.get(("z_coordinates orography", yx_grid), ()):
                DataVariableMetadata.formula_terms(
                    all_variables[z], f"orog: {orog_name}"
                )

        self.data_variables = data_variables
        self.variables = all_variables

        # Verbosity
        if verbose == 1:
            print(repr(self))
        elif verbose == 2:
            print(self)
        elif verbose == 3:
            self.dump()
        elif verbose == 4:
            self.dump(metadata=True)
        elif verbose >= 5 or verbose == -1:
            self.dump(data=True)

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        self.close()

    def __getitem__(self, path: str):
        """Get a data or metadata variable or the File from its path.

        Paths may start with ``.``, ``/``, or ``./``, and a trailing
        ``/`` is ignored. A path may be an empty string.

        """
        if not isinstance(path, str):
            raise TypeError("path must be a string")

        key = path
        if key.startswith("."):
            key = key[1:]

        if key.startswith("/"):
            key = key[1:]

        if key.endswith("/"):
            key = key[:-1]

        if not key:
            return self

        if "/" in key:
            raise KeyError(f"Nested paths are not supported: {path!r}")

        return self.variables[key]

    def __iter__(self):
        """Return an iterator over the variable mapping keys."""
        return iter(self.variables)

    def __len__(self):
        """The number of variables.

        Includes data variables, dimension scale, and metadata
        variables.

        """
        return len(self.variables)

    def __repr__(self):
        n_data = len(self.data_variables)
        n_metadata = len(self.variables) - n_data

        pd = "" if n_data == 1 else "s"
        pm = "" if n_metadata == 1 else "s"

        return (
            f"<{__package__}.{self.__class__.__name__}: {self.filename}, "
            f"{n_data} data variable{pd}, "
            f"{n_metadata} metadata variable{pm}>"
        )

    def __str__(self):
        data_variables = self.data_variables
        out = [repr(self)]
        out.append("Data variables:")
        out.extend(
            f"    {name}: {var!r}"
            for name, var in self.variables.items()
            if name in data_variables
        )
        out.append("Metadata variables:")
        out.extend(
            f"    {name}: {var!r}"
            for name, var in self.variables.items()
            if name not in data_variables
        )
        return "\n".join(out)

    def dump(self, display=True, data=False, metadata=False, _level=0):
        """A full description of the dataset.

        :Parameters:

            display: `bool`, optional
                If False then return the description as a string. By
                default the description is printed.

            data: `bool`, optional
                If True then include a summary of each data and
                metadata variable's data array. If False (the default)
                then don't include these data summaries.

            metadata: `bool`, optional
                If True then include a summary of each metadata
                variable's data array. If False (the default) then
                don't include these data summaries. Note that the
                metadata variables' data arrays are already in memory.

        :Returns:

            `None` or `str`
                The description. If *display* is True then the
                description is printed and `None` is
                returned. Otherwise the description is returned as a
                string.

        """
        indent = "    "
        i0 = indent * _level
        i1 = indent * (_level + 1)
        i2 = indent * (_level + 2)

        lines = [f"{i0}{self!r}"]

        # Attributes
        if self.attrs:
            lines.append(f"{i1}Attributes:")
            lines.extend(
                f"{i2}{name}: {value!r}" for name, value in self.attrs.items()
            )

        # Data
        if self.data_variables:
            lines.append(f"{i1}Data variables:")
            lines.extend(
                var.dump(
                    display=False,
                    data=data,
                    _level=_level + 2,
                )
                for name, var in self.variables.items()
                if name in self.data_variables
            )

        # Metadata variables
        if len(self.variables) > len(self.data_variables):
            lines.append(f"{i1}Metadata variables:")
            lines.extend(
                var.dump(
                    display=False,
                    data=data or metadata,
                    _level=_level + 2,
                )
                for name, var in self.items()
                if name not in self.data_variables
            )

        out = "\n".join(lines)
        if not display:
            return out

        print(out)

    @property
    def consolidated_metadata(self):
        """Whether the metadata are in a contiguous block.

        Metadata in this context comprises the lookup headers and any
        extra data.

        :Returns:

            `bool`

        """
        # FF files have consolidated_metadata there is no extra data
        if self.fmt == "FF":
            return not self.has_extra_data

        # PP files have consolidated_metadata is there is only
        # one lookup header with no extra data
        data_variables = self.data_variables
        if len(data_variables) > 1:
            return False

        if not len(data_variables):
            return True

        var = self[data_variables[0]]
        if len(var.chunk_records) > 1:
            return False

        return not var.has_extra_data

    @property
    def has_extra_data(self):
        """Whether any data variables have extra data.

        :Returns:

            `bool`

        """
        for name in self.data_variables:
            if self[name].has_extra_data:
                return True

        return False

    @property
    def userblock_size(self):
        """Size of the user block in bytes (currently always 0).

        Provided for compatability with the `pyfive` API.

        :Returns:

            `int`

        """
        return 0

    def close(self):
        """Close the underlying dataset reader.

        However, the reader is not closed if it was opened externally,
        i.e. if the *filename* argument to `File` was a file-like
        object.

        :Returns:

            `None`

        """
        # Keep _reader reference so variables can re-open on demand
        # after close.
        if self._owns_reader and self._reader is not None:
            self._reader.close()

    def get_parallelism(self):
        """Get the data variable chunk read parallelism configurations.

        .. seealso:: `set_parallelism`

        :Returns:

            `dict`
                For each data variable, the "thread_count" and
                "cat_range_allowed" parameters to be used when
                accessing the data. See `set_parallelism` for details.

        """
        return {
            name: self[name].get_parallelism() for name in self.data_variables
        }

    def get_lazy_view(self, name):
        """Return a lazy view of the data variable.

        Simply returns the data variable object.

        Provided for compatability with the `pyfive` API.

        :Parameters:

            name: `str`

        :Returns:

            `DataVariable`

        """
        logger.info(
            "get_lazy_view is not supported; returning normal variable view"
        )
        return self[name]

    def items(self):
        """A set-like object providing a view on the dataset's items."""
        return self.variables.items()

    def set_parallelism(self, max_thread_count=0, cat_range_allowed=True):
        """Configure data variable chunk read parallelism.

        .. seealso:: `get_parallelism`

        :Parameters:

            max_thread_count: `int`, optional
                The number of concurrent worker threads to use for
                reading the data chunks of each variable. If ``0``
                (the default) then the reading of data chunks runs
                sequentially in the main thread. For each varable, the
                number of threads actually used will never be greater
                than the number of data chunks, regardless of the
                value of *max_thread_count*.

            cat_range_allowed: `bool`, optional
                If True (the default), uses fsspec's bulk range
                fetching to download multiple data chunks concurrently
                in a single network request. Ignored for non-fsspec
                reader. Set to False to force sequential chunk
                loading. Defaults to True.

        :Returns:

            `None`

        """
        # Set parallelism on data variables
        for name in self.data_variables:
            self[name].set_parallelism(max_thread_count, cat_range_allowed)


class DataVariableMetadata:
    """Creates metadata variables and data variable attributes.

    Only metadata variables that do not already exist will be created.

    The returned instance's `name`, `attrs`, and `DIMENSION_LIST`
    attributes may be used to create a `DataVariable` instance.

    **Initialisation**

    :Parameters:

        data_variable_meta: `dict`
            The data variable meta dictionary from the variable index
            list.

        all_variables: `dict`
            The dictionary of all (i.e. data and metadata) variables.

        file_obj: `File`
            The parent `File` instance.

        cache: `dict`
            The cache of metadata `Variable` and `DimensionScale`
            instance names for the entire dataset. The dictionary keys
            are typically derived from lookup header values.

        Netcdf4Dimid: `list`
            A single-element list containing the next available
            "_NetCDF4Dimid" attribute value for `DimensionScale`
            instances.

    """

    def __init__(self, meta, all_variables, file_obj, cache, Netcdf4Dimid):
        # Data variable attributes
        self.attrs = {}

        # Data variable name
        self.name = None

        self.variables = all_variables
        self.data_variable_meta = meta

        self._file_obj = file_obj
        self._height_at_top_of_model = file_obj._height_at_top_of_model
        um_version = file_obj._um_version

        self._cache = cache
        self._Netcdf4Dimid = Netcdf4Dimid

        chunk_records = meta["chunk_records"]
        self._chunk_records = chunk_records

        rec0 = chunk_records[0]  # ["record"]
        int_hdr = rec0.int_hdr
        real_hdr = rec0.real_hdr
        self._int_hdr_dtype = int_hdr.dtype
        self._real_hdr_dtype = real_hdr.dtype

        self._int_hdr = int_hdr
        self._real_hdr = real_hdr

        # ------------------------------------------------------------
        # Set some metadata quantities which are guaranteed to be the
        # same for all records in a variable
        # ------------------------------------------------------------
        LBYR = int_hdr[INDEX_LBYR]
        LBNPT = int_hdr[INDEX_LBNPT]
        LBROW = int_hdr[INDEX_LBROW]
        LBTIM = int_hdr[INDEX_LBTIM]
        LBCODE = int_hdr[INDEX_LBCODE]
        LBPROC = int_hdr[INDEX_LBPROC]
        LBVC = int_hdr[INDEX_LBVC]
        stash = int_hdr[INDEX_LBUSER4]
        LBUSER5 = int_hdr[INDEX_LBUSER5]
        submodel = int_hdr[INDEX_LBUSER7]
        BPLAT = real_hdr[INDEX_BPLAT]
        BPLON = real_hdr[INDEX_BPLON]

        self._lbnpt = LBNPT
        self._lbrow = LBROW
        self._lbtim = LBTIM
        self._lbcode = LBCODE
        self._lbproc = LBPROC
        self._lbvc = LBVC
        self._stash = stash
        self._bplat = BPLAT
        self._bplon = BPLON

        if not LBROW or not LBNPT:
            logger.warn(
                f"WARNING: Skipping STASH code {stash} with LBROW={LBROW}, "
                f"LBNPT={LBNPT}, LBPACK={int_hdr[INDEX_LBPACK]} "
                "(possibly runlength encoded)"
            )  # pragma: no cover
            return

        if stash:
            section, item = divmod(stash, 1000)
            um_stash_source = f"m{submodel:02d}s{section:02d}i{item:03d}"
        else:
            um_stash_source = None

        header_um_version, source = divmod(int_hdr[INDEX_LBSRCE], 10000)
        if header_um_version > 0 and int(um_version) == um_version:
            # Use version derived from from header
            model_um_version = header_um_version
            um_version = header_um_version
        else:
            # Use version provided
            model_um_version = None

        self._um_version = um_version

        # Set source
        source = _lbsrce_model_codes.get(source)
        if source is not None and model_um_version is not None:
            source += f" vn{model_um_version}"

        # ------------------------------------------------------------
        # Set some derived metadata quantities which are (as good as)
        # guaranteed to be the same for all records in a variable
        # ------------------------------------------------------------
        ia, ib = divmod(LBTIM, 100)
        self._lbtim_ib, ic = divmod(ib, 10)

        if ic == 1:
            self._calendar = "gregorian"
        elif ic == 4:
            self._calendar = "365_day"
        else:
            self._calendar = "360_day"

        self._refunits = f"days since {LBYR}-1-1"

        cf_properties = {}
        if source:
            cf_properties["source"] = source

        # ------------------------------------------------------------
        # Set the T, Z, Y and X axis codes. These are guaranteed to be
        # the same for all records in a variable.
        #
        # Note: The T, Z, Y, X axes most commonly map to the time,
        #       height and horizontal Y and horizontal X physical
        #       axes, but this is not always the case! The axiscodes
        #       stored in `_it`, `_iz`, `_ix`, and `iy` tell the whole
        #       story.
        #
        # ------------------------------------------------------------
        if LBCODE == 1 or LBCODE == 2:
            # 1 = Unrotated regular lat/long grid
            # 2 = Regular lat/lon grid boxes (grid points are box
            #     centres)
            self._ix = 11
            self._iy = 10
        elif LBCODE == 101 or LBCODE == 102:
            # 101 = Rotated regular lat/long grid
            # 102 = Rotated regular lat/lon grid boxes (grid points
            #       are box centres)
            self._ix = -11  # rotated longitude (not an official axis code)
            self._iy = -10  # rotated latitude  (not an official axis code)
        elif LBCODE >= 10000:
            # Cross section
            self._ix, self._iy = divmod(divmod(LBCODE, 10000)[1], 100)
        else:
            self._ix = None
            self._iy = None

        self._iz = _lbvc_to_axiscode.get(LBVC)

        # Set _it from the calendar type
        if self._iy in (20, 23) or self._ix in (20, 23):
            # Time is dealt with by x or y
            self._it = None
        elif self._calendar == "gregorian":
            self._it = 20
        else:
            self._it = 23

        self._cf_info = {}

        # The STASH code has been set in the PP header, so try to find
        # its standard_name from the conversion table
        um_condition = None
        long_name = None
        standard_name = None
        for (
            long_name,
            units,
            valid_from,
            valid_to,
            standard_name,
            cf_info,
            um_condition,
        ) in stash_records(submodel, stash):
            # Check that conditions are met
            if not self.test_um_version(valid_from, valid_to, um_version):
                continue

            if um_condition:
                if not self.test_um_condition(um_condition):
                    continue

            # Still here? Then we have our standard_name, etc.
            if standard_name:
                cf_properties["standard_name"] = standard_name

            cf_properties["long_name"] = long_name.rstrip()

            if units:
                cf_properties["units"] = units

            self._cf_info = cf_info

            break

        if um_stash_source is not None:
            cf_properties["um_stash_source"] = um_stash_source
            identity = f"UM_{um_stash_source}_vn{um_version}"
        else:
            identity = f"UM_{submodel}_fc{int_hdr[INDEX_LBFC]}_vn{um_version}"

        if um_condition:
            identity += f"_{um_condition}"

        cf_properties["um_identity"] = identity

        if long_name is None:
            # Make sure that we always have a long_name
            cf_properties["long_name"] = identity

        # Set the data variable name
        self.name = self.add_to_variables(identity, "data_variable")

        # ------------------------------------------------------------
        # Unique headers for the 'T' and 'Z' axes
        # ------------------------------------------------------------
        shape = meta["shape"]
        axis_order = meta["axis_order"]
        has_z_axis = "z" in axis_order

        if has_z_axis:
            nz = shape[1]
            t_recs = chunk_records[::nz]
            z_recs = chunk_records[:nz]

            # The 'Z' headers might be in the wrong order (i.e. not in the
            # order that we want the coordinate arrays to be), so let's
            # get them in correct order.
            #            z_recs = sorted(z_recs, key=lambda x: x["chunk_coords"])
            #            z_recs = sorted(z_recs, key=lambda x: x["record"].chunk_coords)
            z_recs = sorted(z_recs, key=lambda x: x.chunk_coords)
        else:
            z_recs = []
            t_recs = chunk_records

        #        z_recs = [chunk_rec["record"] for chunk_rec in z_recs]
        #        t_recs = [chunk_rec["record"] for chunk_rec in t_recs]

        self._z_recs = z_recs
        self._t_recs = t_recs

        self._axis = {}

        LBUSER5 = rec0.int_hdr[INDEX_LBUSER5]

        self._z_axis = "z"

        cf_properties["runid"] = self.runid()
        cf_properties["lbproc"] = str(LBPROC)
        cf_properties["lbtim"] = str(LBTIM)
        cf_properties["lbcode"] = str(LBCODE)
        cf_properties["lbvc"] = str(LBVC)
        cf_properties["stash_code"] = str(stash)
        cf_properties["submodel"] = str(submodel)

        # Convert the UM version to a string and provide it as a CF
        # property. E.g. 405 -> '4.5', 606.3 -> '6.6.3', 1002 ->
        # '10.2'
        #
        # Note: We don't just do `divmod(self._um_version, 100)`
        #       because if self._um_version has a fractional part then
        #       it would likely get altered in the divmod calculation.
        a, b = divmod(int(um_version), 100)
        fraction = str(um_version).split(".")[-1]
        um = f"{a}.{b}"
        if fraction != "0" and fraction != str(um_version):
            um += f".{fraction}"

        cf_properties["um_version"] = um

        # Set data variable attribtues
        self.attrs.update(cf_properties)

        # Store the definition of the data varible's Y-X grid
        self._yx_grid_key = (
            "yx_grid",
            LBROW,
            LBNPT,
            int_hdr[INDEX_LBHEM],
            LBCODE,
            BPLAT,
            BPLON,
            real_hdr[INDEX_BGOR],
            real_hdr[INDEX_BDX],
            real_hdr[INDEX_BZX],
            real_hdr[INDEX_BDY],
            real_hdr[INDEX_BZY],
        )

        # Store an orography variable name (this is used to
        # potentially add an "orog" formula term to vertical
        # coordinates)
        if stash == 33:
            self._cache.setdefault(
                ("orography_variables", self._yx_grid_key), []
            ).append(self.name)

        # --------------------------------------------------------
        # Get the extra data for this group
        # --------------------------------------------------------
        extra = rec0.extra_data
        self.extra = extra

        # --------------------------------------------------------
        # Create the 'T' dimension coordinate
        # --------------------------------------------------------
        axiscode = self._it
        if axiscode is not None:
            self.time_coordinate(axiscode)

        # --------------------------------------------------------
        # Create the 'Z' dimension coordinate
        # --------------------------------------------------------
        axiscode = self._iz
        if has_z_axis and axiscode is not None:
            dim_ncvar = None

            # Get 'Z' coordinate from LBVC
            if axiscode == 3:
                dim_ncvar = self.atmosphere_hybrid_sigma_pressure_coordinate(
                    axiscode
                )
            elif axiscode == 2 and "height" in self._cf_info:
                # Create the height coordinate from the information
                # given in the STASH to standard_name conversion table
                height, units = self._cf_info["height"]
                dim_ncvar = self.size_1_height_coordinate(height, units)
            elif axiscode == 14:
                dim_ncvar = self.atmosphere_hybrid_height_coordinate(axiscode)
            else:
                dim_ncvar = self.z_coordinate(axiscode)

            # Create a model_level_number auxiliary coordinate
            #
            # Relevant LBVC codes
            # -------------------
            #   2  Depth
            #   9  Hybrid pressure
            #  65  Hybrid height
            LBLEV = int_hdr[INDEX_LBLEV]
            if LBVC in (2, 9, 65) or LBLEV in (7777, 8888):  # CHECK!
                self._lblev = LBLEV
                self.model_level_number_coordinate(aux=dim_ncvar is not None)

        # --------------------------------------------------------
        # Create the 'Y' dimension coordinate
        # --------------------------------------------------------
        axiscode = self._iy
        if axiscode is not None:
            if axiscode in (20, 23):
                # 'Y' axis is time-since-reference-date
                if extra.get("y") is not None:
                    self.time_coordinate_from_extra_data(axiscode, "y")
                else:
                    LBUSER3 = int_hdr[INDEX_LBUSER3]
                    self._lbuser3 = LBUSER3
                    if LBUSER3 == LBROW:
                        self.time_coordinate_from_um_timeseries(axiscode, "y")
            else:
                dim_ncvar = self.xy_coordinate(axiscode, "y")
                if axiscode == 13:
                    self.site_coordinates_from_extra_data("y")

        # --------------------------------------------------------
        # Create the 'X' dimension coordinate
        # --------------------------------------------------------
        axiscode = self._ix
        if axiscode is not None:
            if axiscode in (20, 23):
                # X axis is time since reference date
                if extra.get("x") is not None:
                    self.time_coordinate_from_extra_data(axiscode, "x")
                else:
                    LBUSER3 = int_hdr[INDEX_LBUSER3]
                    self._lbuser3 = LBUSER3
                    if LBUSER3 == LBNPT:
                        self._lbuser3 = LBUSER3
                        self.time_coordinate_from_um_timeseries(axiscode, "x")
            else:
                dim_ncvar = self.xy_coordinate(axiscode, "x")
                if axiscode == 13:
                    self.site_coordinates_from_extra_data("x")

        # -10: rotated latitude  (not an official axis code)
        # -11: rotated longitude (not an official axis code)

        if set((self._iy, self._ix)) == set((-10, -11)):
            # ----------------------------------------------------
            # Create a ROTATED_LATITUDE_LONGITUDE grid_mapping
            # variable
            # ----------------------------------------------------
            self.grid_mapping()

        # --------------------------------------------------------
        # Create a RADIATION WAVELENGTH dimension coordinate
        # --------------------------------------------------------
        if has_z_axis:
            try:
                rwl, rwl_units = self._cf_info["below"]
            except (KeyError, TypeError):
                pass
            else:
                self.radiation_wavelength_coordinate(rwl, rwl_units)

                # Set LBUSER5 to zero so that later it is not confused
                # for a pseudolevel
                LBUSER5 = 0

        # ------------------------------------------------------------
        # Create a PSEUDOLEVEL dimension coordinate. This must be done
        # *after* the possible creation of a radiation wavelength
        # dimension coordinate.
        # ------------------------------------------------------------
        if has_z_axis and LBUSER5 != 0:
            self.pseudolevel_coordinate(LBUSER5)

        # Set the cell_methods attribute
        self.cell_methods()

        # Set packing attributes
        self.packing()

        # Set missing value attributes
        self.missing_value()

        # ------------------------------------------------------------
        # Set the data variable's dimension names
        # ------------------------------------------------------------
        dim_names = []
        for axis, size in zip(axis_order, shape):
            if axis in self._axis:
                dim_names.append(self._axis[axis])
            else:
                # Coordinates were not created for this axis, so use
                # an appropriately sized dimension.
                dim = self.dimension("dimension", size)
                dim_names.append(dim)

        self.DIMENSION_LIST = tuple((ncdim,) for ncdim in dim_names)

    def add_to_coordinates(self, name):
        """Add a name the data variable's "coordinates" attribute.

        :Parameters:

            name: `str`
                The variable name to add.

        :Returns:

            `None`

        """
        attrs = self.attrs
        coordinates = attrs.get("coordinates")
        if coordinates:
            coordinates += f" {name}"
        else:
            coordinates = name

        attrs["coordinates"] = coordinates

    def add_to_variables(self, name, default="variable"):
        """Add a variable to the `variables` dictionary.

        The key is defined by *name*, and may have a suffx added to it
        to ensure uniqueness.

        If *name* is a string, then a plae-holder is added to the
        `variables` dictionry, with a value of `None`. This
        expectation is that `None` will get replaced later with a
        variable instance.

        :Parameters:

            name:
                The name of the variable to add. Either a string, or a
                a variable instance that has its name stored in its
                `!name` attribute, or `None`.

            default: `str`, optional
                The variable name to add if no string-valued name is
                available.

        :Returns:

            `str`
                The added, unique name.

        """
        if not (name is None or isinstance(name, str)):
            # 'name' is some sort of variable instance
            var = name
            name = var.name
        else:
            var = None

        if name is None:
            name = default

        counter = 1
        unique_name = name
        while unique_name in self.variables:
            unique_name = f"{name}_{counter}"
            counter += 1

        if var is not None:
            var.name = unique_name

        self.variables[unique_name] = var
        return unique_name

    def atmosphere_hybrid_height_coordinate(self, axiscode):
        """`atmosphere_hybrid_height_coordinate` when not an array axis.

        **From appendix A of UMDP F3**

        From UM Version 5.2, the method of defining the model levels
        in PP headers was revised. At vn5.0 and 5.1, eta values were
        used in the PP headers to specify the levels of model data,
        which was of limited use when plotting data on model
        levels. From 5.2, the PP headers were redefined to give
        information on the height of the level. Given a 2D orography
        field, the height field for a given level can then be
        derived. The height coordinates for PP-output are defined as:

          Z(i,j,k)=Zsea(k)+C(k)*orography(i,j)

        where Zsea(k) and C(k) are height based hybrid coefficients.

          Zsea(k) = eta_value(k)*Height_at_top_of_model

          C(k)=[1-eta_value(k)/eta_value(first_constant_rho_level)]**2
               for levels less than or equal to
               first_constant_rho_level

          C(k)=0.0 for levels greater than first_constant_rho_level

        where eta_value(k) is the eta_value for theta or rho level
        k. The eta_value is a terrain-following height coordinate;
        full details are given in UMDP15, Appendix B.

        The PP headers store Zsea and C as follows :-

          * 46 = bulev = brsvd1  = Zsea of upper layer boundary
          * 47 = bhulev = brsvd2 = C of upper layer boundary
          * 52 = blev            = Zsea of level
          * 53 = brlev           = Zsea of lower layer boundary
          * 54 = bhlev           = C of level
          * 55 = bhrlev          = C of lower layer boundary

        :Parameters:

            axiscode: `int`
                Defines the physical nature of the axis.

        :Returns:

            `str`
                The name dimension coordinate variable.

        """
        z_recs = self._z_recs

        # Zsea
        array_a = tuple(rec.real_hdr[INDEX_BLEV] for rec in z_recs)
        # Zsea lower
        bounds0_a = tuple(rec.real_hdr[INDEX_BRLEV] for rec in z_recs)
        # Zsea upper
        bounds1_a = tuple(rec.real_hdr[INDEX_BRSVD1] for rec in z_recs)

        array_b = tuple(rec.real_hdr[INDEX_BHLEV] for rec in z_recs)
        bounds0_b = tuple(rec.real_hdr[INDEX_BHRLEV] for rec in z_recs)
        bounds1_b = tuple(rec.real_hdr[INDEX_BRSVD2] for rec in z_recs)

        key = (
            "atmosphere_hybrid_height_coordinate",
            array_a,
            bounds0_a,
            bounds1_a,
            array_b,
            bounds0_b,
            bounds1_b,
            self._yx_grid_key,
        )
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            # Height at top of atmosphere
            toa_height = self._height_at_top_of_model
            if toa_height is None:
                pseudolevels = any(
                    [rec.int_hdr[INDEX_LBUSER5] for rec in z_recs]
                )
                if pseudolevels:
                    # Pseudolevels and atmosphere hybrid height
                    # coordinates are both present => can't reliably
                    # infer height. This is due to a current
                    # limitation in the C library that means it can
                    # only create Z-T aggregations, rather than the
                    # required Z-T-P aggregations.
                    toa_height = -1

            array_a = np.array(array_a)
            bounds0_a = np.array(bounds0_a)
            bounds1_a = np.array(bounds1_a)
            bounds_a = self.bounds_array(bounds0_a, bounds1_a)

            array_b = np.array(array_b)
            bounds0_b = np.array(bounds0_b)
            bounds1_b = np.array(bounds1_b)
            bounds_b = self.bounds_array(bounds0_b, bounds1_b)

            if toa_height is None:
                toa_height = bounds1_a.max()
                if toa_height <= 0:
                    toa_height = None
            elif toa_height <= 0:
                toa_height = None
            else:
                toa_height = np.float64(toa_height)

            # atmosphere_hybrid_height_coordinate dimension coordinate
            if toa_height is None:
                d = DimensionScale(
                    name="atmosphere_hybrid_height_coordinate",
                    size=array_a.size,
                    file_obj=self._file_obj,
                    Netcdf4Dimid=self._Netcdf4Dimid,
                )
                dim_ncvar = self.add_to_variables(d, "dimension")
                self._axis["z"] = dim_ncvar

                bounds_ncvar = None
            else:
                array = array_a / toa_height
                bounds = bounds_a / toa_height

                dc = DimensionScale(
                    data=array,
                    axiscode=axiscode,
                    attrs={"bounds": None},
                    file_obj=self._file_obj,
                    Netcdf4Dimid=self._Netcdf4Dimid,
                )
                dim_ncvar = self.add_to_variables(dc, "dimension_coordinate")
                self._axis["z"] = dim_ncvar

                bounds_dim = self.bounds_dim(bounds)
                dc_bounds = Variable(
                    name=f"{dim_ncvar}_bounds",
                    data=bounds,
                    DIMENSION_LIST=((self._axis["z"],), (bounds_dim,)),
                )
                bounds_ncvar = self.add_to_variables(dc_bounds)

                dc.attrs["bounds"] = bounds_ncvar

            self._cache.setdefault(
                ("z_coordinates orography", self._yx_grid_key), []
            ).append(dim_ncvar)

            if bounds_ncvar is not None:
                self._cache.setdefault(
                    ("z_coordinates orography", self._yx_grid_key), []
                ).append(bounds_ncvar)

            # "a" domain ancillary
            da_a = Variable(
                name="atmosphere_hybrid_height_coordinate_a",
                data=array_a,
                attrs={
                    "long_name": "height based hybrid coeffient a",
                    "units": "m",
                    "bounds": None,
                },
                DIMENSION_LIST=((self._axis["z"],),),
            )
            self.add_to_variables(da_a)

            # "a" domain ancillary bounds
            bounds_dim = self.bounds_dim(bounds)
            da_a_bounds = Variable(
                name=f"{da_a.name}_bounds",
                data=bounds_a,
                DIMENSION_LIST=((self._axis["z"],), (bounds_dim,)),
            )
            self.add_to_variables(da_a_bounds)

            da_a.attrs["bounds"] = da_a_bounds.name

            # "b" domain ancillary
            da_b = Variable(
                name="atmosphere_hybrid_height_coordinate_b",
                data=array_b,
                attrs={
                    "long_name": "height based hybrid coeffient b",
                    "units": "1",
                    "bounds": None,
                },
                DIMENSION_LIST=((self._axis["z"],),),
            )
            self.add_to_variables(da_b)

            # "b" domain ancillary bounds
            bounds_dim = self.bounds_dim(bounds)
            da_b_bounds = Variable(
                name=f"{da_b.name}_bounds",
                data=bounds_b,
                DIMENSION_LIST=((self._axis["z"],), (bounds_dim,)),
            )
            self.add_to_variables(da_b_bounds)
            da_b.attrs["bounds"] = da_b_bounds.name

            # Set the 'forumla terms' attributes on the parent
            # coordinate and coordinate bounds variables
            self.formula_terms(dc, f"a: {da_a.name} b: {da_b.name}")
            self.formula_terms(
                dc_bounds, f"a: {da_a_bounds.name} b: {da_b_bounds.name}"
            )

            self._cache[key] = dim_ncvar
        else:
            self._axis["z"] = dim_ncvar

        self.add_to_coordinates(dim_ncvar)
        return dim_ncvar

    def atmosphere_hybrid_sigma_pressure_coordinate(self, axiscode):
        """`atmosphere_hybrid_sigma_pressure_coordinate`

        Only applicable when not an array axis.

        46 BULEV Upper layer boundary or BRSVD(1)

        47 BHULEV Upper layer boundary or BRSVD(2)

            For hybrid levels:
            - BULEV is B-value at half-level above.
            - BHULEV is A-value at half-level above.

            For hybrid height levels (vn5.2-, Smooth heights)
            - BULEV is Zsea of upper layer boundary
                * If rho level: Zsea for theta level above
            * If theta level: Zsea for rho level above
            - BHLEV is C of upper layer boundary
                * If rho level: C for theta level above
                * If theta level: C for rho level above

        :Parameters:

            axiscode: `int`
                Defines the physical nature of the axis.

        :Returns:

            `str`
                The name dimension coordinate variable.

        """
        items = tuple(self.bz(rec) for rec in self._z_recs)
        key = (
            "atmosphere_hybrid_sigma_pressure_coordinate",
            items,
            self._yx_grid_key,
        )
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            array = []
            bounds = []
            ak_array = []
            ak_bounds = []
            bk_array = []
            bk_bounds = []

            for BLEV, BRLEV, BHLEV, BHRLEV, BULEV, BHULEV in items:
                array.append(BLEV + BHLEV / PSTAR)
                bounds.append([BRLEV + BHRLEV / PSTAR, BULEV + BHULEV / PSTAR])

                ak_array.append(BHLEV)
                ak_bounds.append((BHRLEV, BHULEV))

                bk_array.append(BLEV)
                bk_bounds.append((BRLEV, BULEV))

            array = np.array(array, dtype=float)
            bounds = np.array(bounds, dtype=float)
            ak_array = np.array(ak_array, dtype=float)
            ak_bounds = np.array(ak_bounds, dtype=float)
            bk_array = np.array(bk_array, dtype=float)
            bk_bounds = np.array(bk_bounds, dtype=float)

            # Insert new Z axis
            dc = DimensionScale(
                data=array,
                axiscode=axiscode,
                attrs={"bounds": None},
                file_obj=self._file_obj,
                Netcdf4Dimid=self._Netcdf4Dimid,
            )

            dim_ncvar = self.add_to_variables(dc, "dimension_coordinate")
            self._axis["z"] = dim_ncvar

            bounds_dim = self.bounds_dim(bounds)
            dc_bounds = Variable(
                name=f"{dim_ncvar}_bounds",
                data=bounds,
                DIMENSION_LIST=((self._axis["z"],), (bounds_dim,)),
            )
            self.add_to_variables(dc_bounds)

            dc.attrs["bounds"] = dc_bounds.name

            self._cache.setdefault(
                ("z_coordinates orography", self._yx_grid_key), []
            ).extend((dim_ncvar, dc_bounds.name))

            # "a" domain ancillary
            name = "atmosphere_hybrid_sigma_pressure_coordinate_ak"
            da_a = Variable(
                name=name,
                data=ak_array,
                attrs={"long_name": name, "units": "Pa", "bounds": None},
                DIMENSION_LIST=((self._axis["z"],),),
            )
            self.add_to_variables(da_a)

            # "a" domain ancillary bounds
            bounds_dim = self.bounds_dim(bounds)
            da_a_bounds = Variable(
                name=f"{da_a.name}_bounds",
                data=ak_bounds,
                DIMENSION_LIST=((self._axis["z"],), (bounds_dim,)),
            )
            self.add_to_variables(da_a_bounds)

            da_a.attrs["bounds"] = da_a_bounds.name

            # "b" domain ancillary
            name = "atmosphere_hybrid_sigma_pressure_coordinate_bk"
            da_b = Variable(
                name=name,
                data=bk_array,
                attrs={"long_name": name, "units": "1", "bounds": None},
                DIMENSION_LIST=((self._axis["z"],),),
            )
            self.add_to_variables(da_b)

            # "b" domain ancillary bounds
            bounds_dim = self.bounds_dim(bounds)
            da_b_bounds = Variable(
                name=f"{da_b.name}_bounds",
                data=bk_bounds,
                DIMENSION_LIST=((self._axis["z"],), (bounds_dim,)),
            )
            self.add_to_variables(da_b_bounds)

            da_b.attrs["bounds"] = da_b_bounds.name

            # Set the 'forumla terms' attributes on the parent
            # coordinate and coordinate bounds variables
            self.formula_terms(dc, f"a: {da_a.name} b: {da_b.name}")
            self.formula_terms(
                dc_bounds, f"a: {da_a_bounds.name} b: {da_b_bounds.name}"
            )

            self._cache[key] = dim_ncvar
        else:
            self._axis["z"] = dim_ncvar

        self.add_to_coordinates(dim_ncvar)
        return dim_ncvar

    def bounds_array(self, bounds0, bounds1):
        """Stack two 1-d arrays to create a bounds array.

        The returned array will have a trailing dimension of size 2.

        The leading dimension size and data type are taken from
        *bounds0*.

        :Parameters:

            bounds0: `numpy.ndarray`
                The bounds which are to occupy ``[:, 0]`` in the
                returned bounds array.

            bounds1: `numpy.ndarray`
                The bounds which are to occupy ``[:, 1]`` in the
                returned bounds array.

        :Returns:

            `numpy.ndarray`
                The bounds array.

        """
        bounds = np.empty((bounds0.size, 2), dtype=bounds0.dtype)
        bounds[:, 0] = bounds0
        bounds[:, 1] = bounds1
        return bounds

    def bounds_dim(self, bounds):
        """Get the name for the trailing bounds dimension.

        :Parameters:

            bounds: `nump.ndarray`
                The bounds array.

        :Returns:

            `str`
                The bounds dimension name.

        """
        return self.dimension("bounds", bounds.shape[-1])

    def bz(self, rec):
        """Return Z coordinate information.

        Return the tuple (BLEV, BRLEV, BHLEV, BHRLEV, BULEV, BHULEV)
        for the given record.

        :Parameters:

            rec: `RecordInfo`

        :Returns:

            `tuple`

        """
        real_hdr = rec.real_hdr
        return tuple(
            real_hdr[INDEX_BLEV : INDEX_BHRLEV + 1].tolist()
            + real_hdr[INDEX_BRSVD1 : INDEX_BRSVD2 + 1].tolist()
        )

    def cell_methods(self):
        """Create a cell methods attribute.

        LBPROC Processing code. This indicates what processing has
        been done to the basic ﬁeld. It should be 0 if no processing
        has been done, otherwise add together the relevant numbers
        from the list below:

        1 Difference from another experiment.
        2 Difference from zonal (or other spatial) mean.
        4 Difference from time mean.
        8 X-derivative (d/dx)
        16 Y-derivative (d/dy)
        32 Time derivative (d/dt)
        64 Zonal mean ﬁeld
        128 Time mean ﬁeld
        256 Product of two ﬁelds
        512 Square root of a ﬁeld
        1024 Difference between ﬁelds at levels BLEV and BRLEV
        2048 Mean over layer between levels BLEV and BRLEV
        4096 Minimum value of ﬁeld during time period
        8192 Maximum value of ﬁeld during time period
        16384 Magnitude of a vector, not speciﬁcally wind speed
        32768 Log10 of a ﬁeld
        65536 Variance of a ﬁeld
        131072 Mean over an ensemble of parallel runs

        :Returns:

            `None`

        """
        cell_methods = []
        LBPROC = self._lbproc
        LBTIM_IB = self._lbtim_ib
        tmean_proc = 0

        # ------------------------------------------------------------
        # Ensemble mean cell method
        # ------------------------------------------------------------
        if 131072 <= LBPROC < 262144:
            cell_methods.append("realization: mean")
            LBPROC -= 131072

        if LBTIM_IB in (2, 3) and LBPROC in (128, 192, 2176, 4224, 8320):
            tmean_proc = 128
            LBPROC -= 128

        # ------------------------------------------------------------
        # Area cell methods
        # ------------------------------------------------------------
        # -10: rotated latitude  (not an official axis code)
        # -11: rotated longitude (not an official axis code)
        if self._ix in (10, 11, 12, -10, -11) and self._iy in (
            10,
            11,
            12,
            -10,
            -11,
        ):
            cf_info = self._cf_info

            if "where" in cf_info:
                cell_methods.append("area: mean")

                cell_methods.append(cf_info["where"])
                if "over" in cf_info:
                    cell_methods.append(cf_info["over"])

            if LBPROC == 64:
                cell_methods.append(f"{self._axis['x']}: mean")

            # dch : do special zonal mean as as in pp_cfwrite

        # ------------------------------------------------------------
        # Vertical cell methods
        # ------------------------------------------------------------
        if LBPROC == 2048:
            cell_methods.append(f"{self._axis['z']}: mean")

        # ------------------------------------------------------------
        # Time cell methods
        # ------------------------------------------------------------
        axis = getattr(self, "_time_axis", "time")
        if LBTIM_IB == 0 or LBTIM_IB == 1:
            cell_methods.append(f"{axis}: point")
        elif LBPROC == 4096:
            cell_methods.append(f"{axis}: minimum")
        elif LBPROC == 8192:
            cell_methods.append(f"{axis}: maximum")
        if tmean_proc == 128:
            if LBTIM_IB == 2:
                cell_methods.append(f"{axis}: mean")
            elif LBTIM_IB == 3:
                cell_methods.append(f"{axis}: mean within years")
                cell_methods.append(f"{axis}: mean over years")

        # Set the data variable cell_methods attribute
        if cell_methods:
            self.attrs["cell_methods"] = " ".join(cell_methods)

    def dimension(self, basename, size):
        """Get the name for a dimension, creating it if necessary.

        :Parameters:

            basename: `str`
                The basename of the dimension. The actual dimension
                will have name ``f"{basename}{size}"``.

            size: `int`
                The dimension size.

        :Returns:

            `str`
                The bounds dimension name.

        """
        name = f"{basename}{size}"
        if name in self.variables:
            # Dimension name already exists
            return name

        # Create a new bounds dimension
        d = DimensionScale(
            name=name,
            size=size,
            file_obj=self._file_obj,
            Netcdf4Dimid=self._Netcdf4Dimid,
        )
        name = self.add_to_variables(d)
        return name

    def dtime(self, rec):
        """Return data-time information for a single record.

        Return the tuple (LBYRD, LBMOND, LBDATD, LBHRD, LBMIND) for
        the given record.

        :Parameters:

            rec: `RecordInfo`

        :Returns:

            `tuple`

        **Examples**

        >>> u.dtime(rec)
        (1991, 2, 1, 0, 0)

        """
        return tuple(rec.int_hdr[INDEX_LBYRD : INDEX_LBMIND + 1].tolist())

    @classmethod
    def formula_terms(cls, var, formula_terms):
        """Add to the formula_terms attribute to a varable.

        :Parameters:

            var:
                The variable.

            formula_terms: `str`
                The formula terms to set as the variable's
                "formula_terms" attribute.

        :Returns:

            `None`

        """
        original_ft = var.attrs.get("formula_terms")
        if original_ft is not None:
            formula_terms = f"{original_ft} {formula_terms}"
            var.attrs["formula_terms"] = formula_terms
        else:
            var.setattr("formula_terms", formula_terms)

    def grid_mapping(self):
        """Add packing attributes to a data variable.

        :Returns:

            `None`

        """
        BPLAT = self._bplat
        BPLON = self._bplon
        key = ("grid_mapping", BPLAT, BPLON)
        gm_name = self._cache.get(key)
        if gm_name is None:
            array = np.array("", dtype="S1")
            gm = Variable(
                name="rotated_latitude_longitude",
                data=array,
                attrs={
                    "grid_mapping_name": "rotated_latitude_longitude",
                    "grid_north_pole_latitude": BPLAT,
                    "grid_north_pole_longitude": BPLON,
                },
            )
            gm_name = self.add_to_variables(gm)
            self._cache[key] = gm_name

        self.attrs["grid_mapping"] = gm_name

    def missing_value(self):
        """Add missing_value and _FillValue attributes to a variable.

        :Returns:

            `None`

        """
        int_hdr = self._int_hdr
        real_hdr = self._real_hdr

        missing_value = real_hdr[INDEX_BMDI]
        if missing_value != BMDI_no_missing_data_value:
            if int_hdr[INDEX_LBUSER1] == 2:
                # Must have an integer _FillValue for integer data
                missing_value = missing_value.astype(int_hdr.dtype)

            self.attrs["_FillValue"] = missing_value
            self.attrs["missing_value"] = missing_value

    def model_level_number_coordinate(self, aux=False):
        """Create a model_level_number coordinate.

        :Parameters:

            aux: `bool`
                If True then create an auxiliary coordinate variabel,
                otherwise create a dimension coordinate variable.

        :Returns:

            out: `str` or `None`
                The variable name, or `None` if one couldn't be
                created.

        """
        array = tuple(rec.int_hdr[INDEX_LBLEV] for rec in self._z_recs)
        key = ("model_level_number_coordinate", aux, array)
        ncvar = self._cache.get(key)
        if ncvar is None:
            # Still here?
            array = np.array(array)
            if array.min() < 0:
                return

            # Still here?
            axiscode = 5

            # Replace 9999 (surface) with level 0
            array = np.where(array == 9999, 0, array)
            if aux:
                ac = Variable(
                    data=array,
                    axiscode=axiscode,
                    DIMENSION_LIST=((self._axis["z"],),),
                )
                ncvar = self.add_to_variables(ac, "auxiliary_coordinate")
            else:
                dc = DimensionScale(
                    data=array,
                    axiscode=axiscode,
                    file_obj=self._file_obj,
                    Netcdf4Dimid=self._Netcdf4Dimid,
                )
                ncvar = self.add_to_variables(dc, "dimension_coordinate")

            self._cache[key] = ncvar

        if not aux:
            self._axis["z"] = ncvar

        self.add_to_coordinates(ncvar)
        return ncvar

    def packing(self):
        """Add add_offset and scale_factor attributes to a variable.

        :Returns:

            `None`

        """
        # Treat BMKS as a scale_factor if it is neither 0 nor 1
        int_hdr = self._int_hdr
        real_hdr = self._real_hdr

        scale_factor = real_hdr[INDEX_BMKS]
        if scale_factor != 1.0 and scale_factor != 0.0:
            if int_hdr[INDEX_LBUSER1] == 2:
                # Must have an integer scale_factor for integer data
                scale_factor = scale_factor.astype(int_hdr.dtype)

            self.attrs["scale_factor"] = scale_factor

        # Treat BDATUM as an add_offset if it is not 0
        add_offset = real_hdr[INDEX_BDATUM]
        if add_offset != 0.0:
            if int_hdr[INDEX_LBUSER1] == 2:
                # Must have an integer add_offset for integer data
                add_offset = add_offset.astype(int_hdr.dtype)

            self.attrs["add_offset"] = add_offset

    def pseudolevel_coordinate(self, LBUSER5):
        """Create and return the pseudolevel coordinate.

        :Returns:

            `str`
                The name of the dimension coordinate variable.

        """
        if len(self._z_recs) == 1:
            array = (LBUSER5,)
        else:
            # 'Z' aggregation has been done along the pseudolevel axis
            array = tuple(rec.int_hdr[INDEX_LBUSER5] for rec in self._z_recs)
            self._z_axis = "p"

        key = ("pseudolevel_coordinate", array)
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            # Create new pseudolevel coordinate
            axiscode = 40
            array = np.array(array)
            dc = DimensionScale(
                name="pseudolevel",
                data=array,
                axiscode=axiscode,
                attrs={"long_name": "pseudolevel"},
                file_obj=self._file_obj,
                Netcdf4Dimid=self._Netcdf4Dimid,
            )
            dim_ncvar = self.add_to_variables(dc)

            self._cache[key] = dim_ncvar

        self._axis["z"] = dim_ncvar

        self.add_to_coordinates(dim_ncvar)
        return dim_ncvar

    def radiation_wavelength_coordinate(self, rwl, rwl_units):
        """Creata and return the radiation wavelength coordinate.

        :Returns:

            `str`
                The name of the auxiliary coordinate variable.

        """
        key = ("radiation_wavelength_coordinate", rwl, rwl_units)
        aux_ncvar = self._cache.get(key)
        if aux_ncvar is None:
            # Create new radiation wavelength coordinate
            array = np.array(rwl, dtype=float)
            bounds = np.array((0.0, rwl), dtype=float)

            axiscode = -20
            ac = Variable(
                data=array,
                axiscode=axiscode,
                attrs={"units": rwl_units, "bounds": None},
            )
            aux_ncvar = self.add_to_variables(ac, "auxiliary_coordinate")

            bounds_dim = self.bounds_dim(bounds)
            ac_bounds = Variable(
                name=f"{aux_ncvar}_bounds",
                data=bounds,
                DIMENSION_LIST=((bounds_dim,),),
            )
            bounds_ncvar = self.add_to_variables(ac_bounds)

            ac.attrs["bounds"] = bounds_ncvar

            self._cache[key] = aux_ncvar

        self._axis["r"] = aux_ncvar

        self.add_to_coordinates(aux_ncvar)
        return aux_ncvar

    def runid(self):
        """Decode LBEXP in the lookup header as a runid.

        :Returns:

            `str`
               The runid (e.g. ``'aaa5u'``). If LBEXP is a negative
               integer then that number is returned as a string
               (e.g. ``'-34'``).

        """
        LBEXP = self._int_hdr[INDEX_LBEXP]

        runid = _cache_runid.get(LBEXP)
        if runid is not None:
            # Return the cached decoding
            return runid

        if LBEXP < 0:
            runid = str(LBEXP)
        else:
            # Convert LBEXP to a binary string, filled out to 30 bits
            # with zeros
            bits = bin(LBEXP)
            bits = bits.lstrip("0b").zfill(30)

            # Step through 6 bits at a time, converting each 6 bit
            # chunk into a decimal integer, which is used as an index
            # to the characters lookup list.
            runid = []
            for i in range(0, 30, 6):
                index = int(bits[i : i + 6], 2)
                if index < _n_runid_characters:
                    runid.append(_runid_characters[index])

            runid = "".join(runid)

        _cache_runid[LBEXP] = runid
        return runid

    def size_1_height_coordinate(self, height, units):
        """Create a size-one height coordinate.

        :Parameters:

            height: `float`
                The height. E.g. ``1.5``.

            units: `str`
                The height units. E.g. ``'m'``.

        :Returns:

            `str`
                The name of the dimension coordinate variable.

        """
        axiscode = 2

        # Create the height coordinate from the information given in
        # the STASH to standard_name conversion table
        key = ("size_1_height_coordinate", height, units)
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            array = np.array((height,), dtype=float)
            dc = DimensionScale(
                data=array,
                axiscode=axiscode,
                attrs={"units": units},
                file_obj=self._file_obj,
                Netcdf4Dimid=self._Netcdf4Dimid,
            )
            dim_ncvar = self.add_to_variables(dc, "dimension_coordinate")

            self._cache[key] = dim_ncvar

        self._axis["z"] = dim_ncvar

        self.add_to_coordinates(dim_ncvar)
        return dim_ncvar

    def test_um_condition(self, um_condition):
        """Return `True` if the lookup header satisfies a UM condition.

        :Parameters:

            um_condition: `str`
                A UM condition found from a record in the STASH
                table. E.g. ``'true_latitude_longitude'``,
                ``'rotated_latitude_longitude'``.

        :Returns:

            `bool`
                `True` if a field satisfies the condition specified,
                `False` otherwise.

        """
        LBCODE = self._lbcode
        BPLAT = self._bplat
        BPLON = self._bplon

        if um_condition == "true_latitude_longitude":
            if LBCODE in (1, 2):
                return True

            # Check pole location in case of incorrect LBCODE
            if abs(BPLAT - 90.0) <= ATOL + RTOL * 90.0 and abs(BPLON) <= ATOL:
                return True

        elif um_condition == "rotated_latitude_longitude":
            if LBCODE in (101, 102, 111):
                return True

            # Check pole location in case of incorrect LBCODE
            if not (
                abs(BPLAT - 90.0) <= ATOL + RTOL * 90.0 and abs(BPLON) <= ATOL
            ):
                return True

        else:
            raise ValueError(
                "Unknown UM condition in STASH code conversion table: "
                f"{um_condition!r}"
            )

        # Still here? Then the condition has not been satisfied.
        return False

    def test_um_version(self, valid_from, valid_to, um_version):
        """Return `True` if a UM version is within the given range.

        :Parameters:

            valid_from: `int` or `float` or `None`
                The "valid from" version. Set to `None` if there is no
                lower limit. E.g. ``401``, ``606.3``.

            valid_to: `int or  `float` or `None`
                The "valid to" version. Set to `None` if there is no
                upper limit. E.g. ``401``, ``606.3``.

            um_version: `int` or `float`
                The UM version to test against the *valid_from* and
                *valid_to* range. E.g. ``405``, ``606.1``.

        :Returns:

            `bool`
                `True` if the UM version is within the range, `False`
                otherwise.

        """
        if valid_to is None:
            if valid_from is None:
                return True

            if valid_from <= um_version:
                return True

        elif valid_from is None:
            if um_version <= valid_to:
                return True

        elif valid_from <= um_version <= valid_to:
            return True

        return False

    def time_coordinate(self, axiscode):
        """Return the T dimension coordinate.

        :Parameters:

            axiscode: `int`
                Defines the physical nature of the axis.

        :Returns:

            `str`
                The name dimension coordinate variable.

        """
        t_recs = self._t_recs

        vtimes = tuple(self.time_since_vtime(rec) for rec in t_recs)
        dtimes = tuple(self.time_since_dtime(rec) for rec in t_recs)
        key = (
            "time_coordinate",
            self._refunits,
            self._calendar,
            self._lbtim,
            vtimes,
            dtimes,
        )
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            # Create new 'T' coordinate
            vtimes = np.array(vtimes, dtype=float)
            dtimes = np.array(dtimes, dtype=float)

            if np.isnan(vtimes.sum()) or np.isnan(dtimes.sum()):
                return  # ppp

            IB = self._lbtim_ib

            if IB <= 1 or vtimes.item(0) >= dtimes.item(0):
                # Only the validity time (T1) is valid
                array = vtimes
                bounds = None
                climatology = False
            elif IB == 3:
                # The field is a time mean from T1 to the data time
                # (T2) for each year from LBYR to LBYRD
                ctimes = np.array(
                    [
                        self.time_since_climatological_dtime(rec)
                        for rec in t_recs
                    ]
                )
                array = 0.5 * (vtimes + ctimes)
                bounds = self.bounds_array(vtimes, dtimes)
                climatology = True
            else:
                # One of:
                # - the ﬁeld is a time mean between T1 and T2, or
                #   represents a sequence of times between T1 and T2.
                # - the ﬁeld is a difference between ﬁelds valid at T1
                #   and T2 (in sense T2-T1).
                # - the ﬁeld is a mean daily cycle between T2 and T1
                array = 0.5 * (vtimes + dtimes)
                bounds = self.bounds_array(vtimes, dtimes)
                climatology = False

            dc = DimensionScale(
                data=array,
                axiscode=axiscode,
                attrs={"units": self._refunits, "calendar": self._calendar},
                file_obj=self._file_obj,
                Netcdf4Dimid=self._Netcdf4Dimid,
            )
            dim_ncvar = self.add_to_variables(dc, "dimension_coordinate")
            self._axis["t"] = dim_ncvar

            if bounds is not None:
                bounds_dim = self.bounds_dim(bounds)
                dc_bounds = Variable(
                    name=f"{dim_ncvar}_bounds",
                    data=bounds,
                    DIMENSION_LIST=((self._axis["t"],), (bounds_dim,)),
                )
                bounds_ncvar = self.add_to_variables(dc_bounds)

                if climatology:
                    dc.setattr("climatology", bounds_ncvar)
                else:
                    dc.setattr("bounds", bounds_ncvar)

            self._cache[key] = dim_ncvar
        else:
            self._axis["t"] = dim_ncvar

        self._time_axis = dim_ncvar

        self.add_to_coordinates(dim_ncvar)
        return dim_ncvar

    def site_coordinates_from_extra_data(self, axis):
        """Create site-related coordinates from extra data.

        :Parameters:

            axis: `str`
                Which type of axis to create the site coordinate for:
                ``'x'`` or ``'y'``.

        :Returns:

            `None`

        """
        # Create coordinate from extra data
        for site_axis, standard_name, units in zip(
            ("x", "y"),
            ("longitude", "latitude"),
            ("degrees_east", "degrees_north"),
        ):
            lower_bounds = self.extra.get(f"{site_axis}_domain_lower_bound")
            upper_bounds = self.extra.get(f"{site_axis}_domain_upper_bound")
            if lower_bounds is None or upper_bounds is None:
                continue

            # Still here?
            bounds = self.bounds_array(lower_bounds, upper_bounds)
            array = np.average(bounds, axis=1)

            key = (
                "site_coordinates_from_extra_data",
                site_axis,
                tuple(array.tolist()),
                tuple(lower_bounds.tolist()),
                tuple(upper_bounds.tolist()),
            )
            aux_ncvar = self._cache.get(key)
            if aux_ncvar is None:
                ac = Variable(
                    name=standard_name,
                    data=array,
                    attrs={
                        "standard_name": standard_name,
                        "long_name": "region limit",
                        "units": units,
                        "bounds": None,
                    },
                    DIMENSION_LIST=((self._axis[axis],),),
                )
                aux_ncvar = self.add_to_variables(ac)

                bounds_dim = self.bounds_dim(bounds)
                ac_bounds = Variable(
                    name=f"{aux_ncvar}_bounds",
                    data=bounds,
                    DIMENSION_LIST=((self._axis[axis],), (bounds_dim,)),
                )
                ac_bounds_ncvar = self.add_to_variables(ac_bounds)

                ac.attrs["bounds"] = ac_bounds_ncvar

                self._cache[key] = aux_ncvar

            self.add_to_coordinates(aux_ncvar)

        array = self.extra.get("domain_title")
        if array is not None:
            key = ("region_coordinate", tuple(array.tolist()))
            aux_ncvar = self._cache.get(key)
            if aux_ncvar is None:
                ac = Variable(
                    name="region",
                    data=array,
                    DIMENSION_LIST=((self._axis[axis],),),
                )
                aux_ncvar = self.add_to_variables(ac)
                self._cache[key] = aux_ncvar

            self.add_to_coordinates(aux_ncvar)

    def time_coordinate_from_extra_data(self, axiscode, axis):
        """Create the time coordinate from extra data and return it.

        :Returns:

            `str`
                The coordinate variable name.

        """
        extra = self.extra
        array = extra[axis]
        lower_bounds = extra.get(f"{axis}_lower_bound")
        upper_bounds = extra.get(f"{axis}_lupper_bound")

        lbounds = lower_bounds
        if lbounds is not None:
            lbounds = tuple(lower_bounds.tolist())

        ubounds = upper_bounds
        if ubounds is not None:
            ubounds = tuple(upper_bounds.tolist())

        calendar = self._calendar
        if calendar == "360_day":
            units = "days since 0-1-1"
        elif calendar == "gregorian":
            units = "days since 1752-09-13"
        elif calendar == "365_day":
            units = "days since 1752-09-13"

        key = (
            "time_coordinate_from_extra_data",
            units,
            calendar,
            tuple(array.tolist()),
            lbounds,
            ubounds,
        )

        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            # Create time domain axis
            dc = DimensionScale(
                data=array,
                axiscode=axiscode,
                attrs={"units": units, "calendar": calendar},
                file_obj=self._file_obj,
                Netcdf4Dimid=self._Netcdf4Dimid,
            )
            dim_ncvar = self.add_to_variables(dc)

            self._axis[axis] = dim_ncvar
            self._time_axis = dim_ncvar

            if lower_bounds is not None and upper_bounds is not None:
                bounds = self.bounds_array(lower_bounds, upper_bounds)
                bounds_dim = self.bounds_dim(bounds)
                dc_bounds = Variable(
                    name=f"{dim_ncvar}_bounds",
                    data=bounds,
                    DIMENSION_LIST=((self._axis[axis],), (bounds_dim,)),
                )
                dc_bounds_ncvar = self.add_to_variables(dc_bounds)

                dc.setattr("bounds", dc_bounds_ncvar)

            self._cache[key] = dim_ncvar
        else:
            self._axis[axis] = dim_ncvar

        self.add_to_coordinates(dim_ncvar)
        return dim_ncvar

    def time_coordinate_from_um_timeseries(self, axiscode, axis):
        """Create the time coordinate from a timeseries field.

        :Returns:

            `str`
                The coordinate variable name.

        """
        # This PP/FF field is a timeseries. The validity time is taken
        # to be the time for the first sample, the data time for the
        # last sample, with the others evenly between.
        #        rec = self._chunk_recs[0]["record"]
        rec = self._chunk_records[0]
        vtime = self.time_since_vtime(rec)
        dtime = self.time_since_dtime(rec)

        size = np.float64(self._lbuser3 - 1.0)
        delta = (dtime - vtime) / size

        calendar = self._calendar
        if calendar == "360_day":
            units = "days since 0-1-1"
        elif calendar == "gregorian":
            units = "days since 1752-09-13"
        elif calendar == "365_day":
            units = "days since 1752-09-13"

        array = np.arange(vtime, vtime + delta * size, size, dtype=float)

        dc = DimensionScale(
            data=array,
            axiscode=axiscode,
            attrs={"units": units, "calendar": calendar},
            file_obj=self._file_obj,
            Netcdf4Dimid=self._Netcdf4Dimid,
        )
        dim_ncvar = self.add_to_variablesd(dc)

        self._axis[axis] = dim_ncvar
        self._time_axis = dim_ncvar

        self.add_to_coordinates(dim_ncvar)
        return dim_ncvar

    def time_since_climatological_dtime(self, rec):
        """Return elapsed time since the climatological data time.

        :Parameters:

            rec: `RecordInfo`

        :Returns:

            `float`
                The elapsed time, in units defined by `_refunits` and
                `_calendar`.

        """
        calendar = self._calendar
        refunits = self._refunits

        LBVTIME = self.vtime(rec)
        LBDTIME = self.dtime(rec)

        key = ("ctime", LBVTIME, LBDTIME, refunits, calendar)
        ctime = _cache_date2num.get(key)
        if ctime is not None:
            return ctime

        import cftime

        LBDTIME = list(LBDTIME)
        LBDTIME[0] = LBVTIME[0]

        ctime = cftime.datetime(*LBDTIME, calendar=calendar)
        if ctime < cftime.datetime(*LBVTIME, calendar=calendar):
            LBDTIME[0] += 1
            ctime = cftime.datetime(*LBDTIME, calendar=calendar)

        ctime = cftime.date2num(ctime, refunits, calendar)

        _cache_date2num[key] = ctime
        return ctime

    def time_since_dtime(self, rec):
        """Return the elapsed time since the data time.

        :Parameters:

            rec: `RecordInfo`

        :Returns:

            `float`
                The elapsed time, in units defined by `_refunits` and
                `_calendar`.

        """
        refunits = self._refunits
        calendar = self._calendar
        LBDTIME = self.dtime(rec)

        key = ("time_since", LBDTIME, refunits, calendar)
        time = _cache_date2num.get(key)
        if time is None:
            import cftime

            # It is important to use the same time_units as vtime
            try:
                time = cftime.date2num(
                    cftime.datetime(*LBDTIME, calendar=calendar),
                    refunits,
                    calendar,
                )
            except ValueError:
                time = np.nan  # ppp

            _cache_date2num[key] = time

        return time

    def time_since_vtime(self, rec):
        """Return the elapsed time since the validity time.

        :Parameters:

            rec: `RecordInfo`

        :Returns:

            `float`
                The elapsed time, in units defined by `_refunits` and
                `_calendar`.

        """
        refunits = self._refunits
        calendar = self._calendar
        LBVTIME = self.vtime(rec)

        key = ("time_since", LBVTIME, refunits, calendar)

        time = _cache_date2num.get(key)
        if time is None:
            import cftime

            # It is important to use the same time_units as dtime
            try:
                time = cftime.date2num(
                    cftime.datetime(*LBVTIME, calendar=calendar),
                    refunits,
                    calendar,
                )
            except ValueError:
                time = np.nan  # ppp

            _cache_date2num[key] = time

        return time

    def vtime(self, rec):
        """Return validity-time information for a single record.

        Return the tuple (LBYR, LBMON, LBDAT, LBHR, LBMIN) for the
        given record.

        :Parameters:

            rec: `RecordInfo`

        :Returns:

            `tuple`

        **Examples**

        >>> u.vtime(rec)
        (1991, 1, 1, 0, 0)

        """
        return tuple(rec.int_hdr[INDEX_LBYR : INDEX_LBMIN + 1].tolist())

    def xy_coordinate(self, axiscode, axis):
        """Create an X or Y dimension coordinate.

        :Parameters:

            axiscode: `int`
                Defines the physical nature of the axis.

            axis: `str`
                Which type of coordinate to create: ``'x'`` or
                ``'y'``.

        :Returns:

            `str`
                The coordinate name.

        """
        real_hdr = self._real_hdr
        if axis == "x":
            delta = real_hdr[INDEX_BDX]
            origin = real_hdr[INDEX_BZX]
            size = self._lbnpt
        else:
            delta = real_hdr[INDEX_BDY]
            origin = real_hdr[INDEX_BZY]
            size = self._lbrow

        key = (
            f"{axis}_coordinate",
            self._lbcode,
            self._int_hdr[INDEX_LBHEM],
            size,
            self._bplat,
            self._bplon,
            real_hdr[INDEX_BGOR],
            origin,
            delta,
        )
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            name = None
            if abs(delta) > ATOL:
                # Create regular coordinates from header items
                if axiscode == 11 or axiscode == -11:
                    origin -= divmod(origin + delta * size, 360.0)[0] * 360
                    while origin + delta * size > 360.0:
                        origin -= 360.0
                    while origin + delta * size < -360.0:
                        origin += 360.0

                array = np.arange(
                    origin + delta,
                    origin + delta * (size + 0.5),
                    delta,
                    dtype=float,
                )

                # Create the coordinate bounds
                if axiscode in (13, 31, 40, 99):
                    # The following axiscodes do not have bounds:
                    # 13 = Site number (set of parallel rows or columns
                    #      e.g.Time series)
                    # 31 = Logarithm to base 10 of pressure in mb
                    # 40 = Pseudolevel
                    # 99 = Other
                    bounds = None
                else:
                    delta_by_2 = 0.5 * delta
                    bounds = self.bounds_array(
                        array - delta_by_2, array + delta_by_2
                    )

            else:
                # Create coordinate from extra data
                array = self.extra.get(axis)
                lower_bounds = self.extra.get(f"{axis}_lower_bound")
                upper_bounds = self.extra.get(f"{axis}_upper_bound")
                if lower_bounds is not None and upper_bounds is not None:
                    bounds = self.bounds_array(lower_bounds, upper_bounds)
                else:
                    bounds = None

                if axiscode == 13:
                    name = _coord_long_name[13]

            dc = DimensionScale(
                name=name,
                data=array,
                axiscode=axiscode,
                file_obj=self._file_obj,
                Netcdf4Dimid=self._Netcdf4Dimid,
            )
            dim_ncvar = self.add_to_variables(dc)

            self._axis[axis] = dim_ncvar

            if bounds is not None:
                bounds_dim = self.bounds_dim(bounds)
                dc_bounds = Variable(
                    name=f"{dim_ncvar}_bounds",
                    data=bounds,
                    DIMENSION_LIST=((self._axis[axis],), (bounds_dim,)),
                )
                bounds_ncvar = self.add_to_variables(dc_bounds)

                dc.setattr("bounds", bounds_ncvar)

            self._cache[key] = dim_ncvar
        else:
            self._axis[axis] = dim_ncvar

        if axiscode in (20, 23):
            self._time_axis = dim_ncvar

        self.add_to_coordinates(dim_ncvar)
        return dim_ncvar

    def z_coordinate(self, axiscode):
        """Create a Z dimension coordinate from BLEV.

        :Parameters:

            axiscode: `int`
                Defines the physical nature of the axis.

        :Returns:

            `str`
                The coordinate name.

        """
        z_recs = self._z_recs

        # layer centre
        array = tuple(rec.real_hdr[INDEX_BLEV] for rec in z_recs)
        # lower level boundary
        bounds0 = tuple(rec.real_hdr[INDEX_BRLEV] for rec in z_recs)
        # bulev
        bounds1 = tuple(rec.real_hdr[INDEX_BRSVD1] for rec in z_recs)

        key = ("z_coordinate", self._lbvc, array, bounds0, bounds1)
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            if _coord_positive.get(axiscode) == "down":
                bounds0, bounds1 = bounds1, bounds0

            array = np.array(array)
            bounds0 = np.array(bounds0)
            bounds1 = np.array(bounds1)
            bounds = self.bounds_array(bounds0, bounds1)

            if (bounds0 == bounds1).all() or np.allclose(
                bounds.min(), PP_RMDI
            ):
                bounds = None
            else:
                bounds = self.bounds_array(bounds0, bounds1)

            dc = DimensionScale(
                data=array,
                axiscode=axiscode,
                file_obj=self._file_obj,
                Netcdf4Dimid=self._Netcdf4Dimid,
            )
            dim_ncvar = self.add_to_variables(dc, "dimension_coordinate")

            self._axis["z"] = dim_ncvar

            if bounds is not None:
                bounds_dim = self.bounds_dim(bounds)
                b = Variable(
                    name=f"{dim_ncvar}_bounds",
                    data=bounds,
                    DIMENSION_LIST=((self._axis["z"],), (bounds_dim,)),
                )
                bounds_ncvar = self.add_to_variables(b)

                # Set the 'bounds' attribute on the parent corodiante
                # variable
                dc.setattr("bounds", bounds_ncvar)

            self._cache[key] = dim_ncvar
        else:
            self._axis["z"] = dim_ncvar

        if axiscode in (20, 23):
            self._time_axis = dim_ncvar

        self.add_to_coordinates(dim_ncvar)
        return dim_ncvar


# Let external callers treat File as pyfive-like File
try:
    import pyfive
except Exception:  # pragma: no cover
    pass
else:
    pyfive.File.register(File)
