from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from pathlib import Path
import posixpath
from typing import Any

import numpy as np

from .core.constants import INT_MISSING_DATA
from .core import detect_file_type, scan_ff_headers, scan_pp_headers
from .core.variables import build_variable_index
from .io.base import ByteReader
from .io.fileobj import FileObjReader
from .io.fsspec_reader import FsspecReader
from .io.local import LocalPosixReader
from .variable import Variable

from .stash_table import stash_records # needs to be lazy

from .lookup_header import _coord_long_name ,_axiscode_to_units,_coord_axis,_coord_positive,_lbvc_to_axiscode,_lbsrce_model_codes,_extra_data_name,_true_latitude_longitude_lbcodes,_rotated_latitude_longitude_lbcodes,_coord_standard_name, _characters

logger = logging.getLogger(__name__)

_cache_runid = {}
_cache_date2num = {}
_cache_ctime = {}

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
        for key, value in super().items():
            yield key, self._coerce_for_items(value)


class DatasetMixin:
    def setattr(self, name, value):
        if isinstance(value, str):
            value = np._bytes(value)

        self.attrs[name] = value
      
    def setattrs_from_axiscode(self, axiscode, set_name_as_standard_name=False)
        if axiscode is None:
            return

        attrs = self.attrs
        
        name = _coord_standard_name.setdefault(axiscode, None)
        if name is not None:
            attrs['standard_name'] = np.bytes_(name)
            if set_name_as_standard_name:
                self.name = name
        else:
            name = _coord_long_name.setdefault(axiscode, None)
            if name is not None:
                attrs['long_name'] = np.bytes_(name)
                    
        axis = _coord_axis.setdefault(axiscode, None)
        if axis is not None:
            attrs['axis'] = np.bytes_(axis)
           
        positive = _coord_positive.setdefault(axiscode, None)
        if positive is not None:
            attrs['positive'] = np.bytes_(positive)

        if axiscode in (20, 23):            
            attrs["units"] = np.bytes_(self._refunits)
            attrs["calendar"] = np.bytes_(self._calendar)
        else:
            units = _axiscode_to_units.setdefault(axiscode, None)
            if units:
                attrs["units"] = np.bytes_(units)
                    

class _DimensionScale(DatasetMixin):
    """Internal pyfive-like dimension-scale dataset for cfdm bridging."""

    def __init__(
            self,
            name=None,
            data=None,
            size=None
            file_obj="File",
            axiscode=None,
            attrs=None, 
    ):
        self.name = name
        self.file = file_obj
        if data is not None:
            arr = np.asarray(data)
            if arr.ndim != 1:
                raise ValueError("Dimension scale data must be 1-D")
            
            self._data = arr
            self.shape = (int(arr.size),)
            self.dtype = arr.dtype
        else:
            self._data = None
            self.shape = (int(size),)
            self.dtype = None
            
        self.maxshape = self.shape
        self.chunks = None

        self.attrs = {}
        self.setattrs_from_axiscode(axiscode, set_name_as_standard_name=True)
        if attrs:
            self.attrs.update(attrs)

        if data is not None:
            self.attrs.update(
                {
                    "CLASS": b"DIMENSION_SCALE",
                    "NAME": b"netCDF dimension coordinate variable",
                    "_Netcdf4Dimid": 0, # TODO not always 0 ??
                }
            )
        else:
            self.attrs.update(
                {
                    "CLASS": b"TODO SOMEthinDIMENSION_SCALE",
                    "NAME": b"netCDF dimension coordinate variable",
                    "_Netcdf4Dimid": 0, # TODO not always 0 ??
                }
            )
            
    def __getitem__(self, key):
        if self._data is not None:
            return self._data[key]

        return np.arange(self.shape[0], dtype=self.dtype)[key]

class _AuxVar(DatasetMixin)::
    """2-D auxiliary coordinate variable (e.g. unrotated latitude/longitude)."""

    def __init__(self, name=None, data=None, axiscode=None, attrs=None,
                 DIMESNION_LIST=None):
        self.name = name
        self._data = data
        self.shape = data.shape
        self.dtype = data.dtype
        self.maxshape = data.shape
        self.chunks = None

        self.attrs = {}
        self.setattrs_from_axiscode(axiscode, set_name_as_standard_name=True)
        if attrs:
            self.attrs.update(attrs)
                
        if DIMENSION_LIST:
            self.attrs['DIMENSION_LIST'] = DIMENSION_LIST
            
    def __getitem__(self, key):
        return self._data[key]


_ATOL = sys.float_info.epsilon


class File(Mapping[str, Variable]):
    """A pyfive-style file handle exposing variables as a Mapping."""

    @staticmethod
    def _local_default_thread_count_from_variable_index(
        variable_index: Mapping[str, Mapping[str, Any]],
    ) -> int:
        """Choose local POSIX default thread count from chunk topology.

        Preference order for representative chunk-count sample:
        1) WGDOS-packed variables
        2) any packed variables
        3) all variables
        """

        def _counts(predicate) -> list[int]:
            counts: list[int] = []
            for meta in variable_index.values():
                attrs = meta.get("attrs", {})
                if predicate(attrs):
                    counts.append(len(meta.get("chunk_records", ())))
            return counts

        chunk_counts = _counts(lambda attrs: bool(attrs.get("is_wgdos_packed", False)))
        if not chunk_counts:
            chunk_counts = _counts(lambda attrs: bool(attrs.get("is_packed", False)))
        if not chunk_counts:
            chunk_counts = [len(meta.get("chunk_records", ())) for meta in variable_index.values()]

        if not chunk_counts:
            return 1

        max_chunks = max(chunk_counts)
        if max_chunks <= 2:
            return 1
        if max_chunks <= 8:
            return 2
        return 4

    def __init__(
        self,
        filename: str | ByteReader | Any,
        mode: str = "r",
        um_version=405,
        height_at_top_of_model=None,
        metadata_buffer_size: int = 1,
        disable_os_cache: bool = False,
        *,
        reader: ByteReader | None = None,
        variable_index: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        if mode != "r":
            raise ValueError("ppfive.File currently supports read-only mode='r'")

        if isinstance(filename, ByteReader):
            if reader is not None:
                raise ValueError("Do not provide both filename as ByteReader and reader=")
            reader = filename
            filename = getattr(reader, "path", "<byte-reader>")
        elif reader is None and hasattr(filename, "read") and hasattr(filename, "seek"):
            reader = FileObjReader(filename)
            filename = getattr(filename, "name", "<fileobj>")

        self.filename = str(Path(filename))
        self.mode = mode

        self._um_version=um_version
        self._height_at_top_of_model=height_at_top_of_model
        
        
        self.metadata_buffer_size = metadata_buffer_size
        self.disable_os_cache = bool(disable_os_cache)
        self._owns_reader = reader is None
        self._reader = reader or LocalPosixReader(
            self.filename,
            disable_os_cache=self.disable_os_cache,
        )
        self._records = []
        self._thread_count = 0
        self._cat_range_allowed = True
        self.parent = None
        self.name = "/"
        self.path = "/"
        self.attrs: dict[str, Any] = {}
        self.groups: dict[str, Any] = {}
        self.dimensions: dict[str, Any] = {}
        self._pyfive_dimension_scales: dict[str, _DimensionScale] = {}
        self._grid_mapping_vars: dict[str, _ScalarVar] = {}

        if variable_index is None:
            file_type = detect_file_type(self._reader)
            self.fmt = file_type.fmt
            self.byte_ordering = file_type.byte_ordering
            self.word_size = file_type.word_size
            if file_type.fmt == "PP":
                self._records = scan_pp_headers(self._reader, file_type)
            else:
                self._records = scan_ff_headers(self._reader, file_type)
            
            if not self._records:
                raise ValueError(
                    f"No valid records found in {self.fmt} file "
                    f"{self.filename}. "
                    f"The file may be corrupted or empty."
                )

            # Default policy: remote readers use 4 threads.
            if isinstance(self._reader, FsspecReader):
                self._thread_count = 4
            
            variable_index = build_variable_index(
                self._records,
                self._reader,
                self.word_size,
                self.byte_ordering,
                parallel_config={
                    "thread_count": self._thread_count,
                    "cat_range_allowed": self._cat_range_allowed,
                },
            )

            # Default policy: local POSIX readers choose 1/2/4 by chunk count.
            if isinstance(self._reader, LocalPosixReader):
                auto_threads = self._local_default_thread_count_from_variable_index(variable_index)
                if auto_threads != self._thread_count:
                    self._thread_count = auto_threads
                    variable_index = build_variable_index(
                        self._records,
                        self._reader,
                        self.word_size,
                        self.byte_ordering,
                        parallel_config={
                            "thread_count": self._thread_count,
                            "cat_range_allowed": self._cat_range_allowed,
                        },
                    )
        else:
            self.fmt = None
            self.byte_ordering = None
            self.word_size = None

        # Dictionary of all dataset variables, keyed by their dataset
        # names
        variables = {}

        cache = {}
        for int_code, meta in tuple(variable_index.items()):
            data_variable = _VariableMetadata(
                meta, variables, self, cache
            )
                        
            # Add a variables entry for athe 'Variable' representing
            # the data variable
            name = data_variable.name
            variables[name] = Variable(
                name=name,
                attrs=_PyfiveAttrs(data_variable.attrs),
                shape=tuple(meta.get("shape", ())),
                dtype=meta.get("dtype"),
                chunk_shape=meta.get("chunk_shape"),
                data_loader=meta.get("data_loader"),
                file=self,
                parent=self,
                chunk_records=list(meta.get("chunk_records", [])),
            )

            # Remove the original variables entry for 'meta'
            variables.pop(int_code)
            
        self.variables = variables
                
    def _build_variables(self, variable_index, cache):
        """TODO"""
        # Dictionary of all dataset variables, keyed by their dataset
        # names
        variables = {}

        for int_code, meta in tuple(variable_index.items()):
            data_variable = _VariableMetadata(
                meta, variables, self, cache
            )
                        
            # Add a variables entry for athe 'Variable' representing
            # the data variable
            name = data_variable.name
            variables[name] = Variable(
                name=name,
                attrs=_PyfiveAttrs(data_variable.attrs),
                shape=tuple(meta.get("shape", ())),
                dtype=meta.get("dtype"),
                chunk_shape=meta.get("chunk_shape"),
                data_loader=meta.get("data_loader"),
                file=self,
                parent=self,
                chunk_records=list(meta.get("chunk_records", [])),
            )

            # Remove the original variables entry for 'meta'
            variables.pop(int_code)
            
        return variables

    @property
    def userblock_size(self) -> int:
        return 0

    @property
    def consolidated_metadata(self) -> bool | None:
        return None

    def get_lazy_view(self, key: str) -> Variable:
        # UM guidance says this cannot be fully implemented yet.
        logger.info("get_lazy_view is not supported; returning normal variable view")
        return self[key]

    def close(self) -> None:
        if self._owns_reader and self._reader is not None:
            self._reader.close()
            # Keep _reader reference so variables can re-open on demand after close.

    def set_parallelism(self, thread_count: int = 5, cat_range_allowed: bool = True):
        """Configure experimental chunk/record read parallelism."""
        if thread_count is None:
            thread_count = 0
        thread_count = int(thread_count)
        if thread_count < 0:
            raise ValueError("thread_count must be >= 0")

        self._thread_count = thread_count
        self._cat_range_allowed = bool(cat_range_allowed)

        if self._records:
            variable_index = build_variable_index(
                self._records,
                self._reader,
                self.word_size,
                self.byte_ordering,
                parallel_config={
                    "thread_count": self._thread_count,
                    "cat_range_allowed": self._cat_range_allowed,
                },
            )
            self._pyfive_dimension_scales = {}
            self._grid_mapping_vars = {}
            self._variables = self._build_variables(variable_index)
            self._refresh_variable_views()

    def __getitem__(self, key: str) -> Variable:
        if not isinstance(key, str):
            raise TypeError("Variable key must be a string")

        path = posixpath.normpath(key)
        if path == ".":
            raise KeyError("'.' does not reference a variable")
        if path.startswith("/"):
            path = path[1:]
        if path.startswith("./"):
            path = path[2:]

        if "/" in path:
            raise KeyError(f"Nested paths are not supported: {key!r}")

        return self.variables[path]

    def items(self):
        return self.variables.items()

    def __iter__(self) -> Iterator[str]:
        return iter(self.variables)

    def __len__(self) -> int:
        return len(self.variables)

    def __enter__(self) -> "File":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __repr__(self) -> str:
        return f'<PP file "{self.filename}" ({len(self)} variables)>'

    def to_reference_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "path": self.filename,
            "variables": {
                name: variable.to_reference_dict()
                for name, variable in self._variables.items()
            },
        }

class _VariableMetadata:
    """TODO"""
    def __init__(
        self,
            data_variable_meta,
            variables,
            file_obj,
            cache
    ):
        """**Initialisation**

        :Parameters:

            height_at_top_of_model: `float`


        """
        # Data variable attributes
        self.attrs = {}

        # Data variable name                
        self.name = None
        
        self.variables = variables
        
        self._file_obj = file_obj
        self._height_at_top_of_model = file_obj._height_at_top_of_model
        um_version =  file_obj._um_version
        
        self._cache = cache
        
        self._recs = [
            rec['record'] for rec in data_variable_meta.chunk_records
        ]

        rec0 = recs[0]        
        int_hdr = rec0.int_hdr
        self._int_hdr_dtype = int_hdr.dtype
        self._real_hdr_dtype = rec0.real_hdr.dtype
        int_hdr = int_hdr.tolist()
        real_hdr = rec0.real_hdr.tolist()

        self._int_hdr = int_hdr
        self._real_hdr = real_hdr

        # ------------------------------------------------------------
        # Set some metadata quantities which are guaranteed to be the
        # same for all records in a variable
        # ------------------------------------------------------------
        LBYR = int_hdr.item(INDEX_LBYR,)
        LBNPT = int_hdr.item(INDEX_LBNPT,)
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
        BDX = real_hdr[INDEX_BDX]
        BDY = real_hdr[INDEX_BDY]

        if not LBROW or not LBNPT:
            logger.warn(
                f"WARNING: Skipping STASH code {stash} with LBROW={LBROW}, "
                f"LBNPT={LBNPT}, LBPACK={int_hdr[INDEX_LBPACK]} " # TODO
                "(possibly runlength encoded)"
            )  # pragma: no cover
            self.field = (None,)
            return

        if stash:
            section, item = divmod(stash, 1000)
            um_stash_source = "m%02ds%02di%03d" % (submodel, section, item)
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
        source = _lbsrce_model_codes.setdefault(source, None)
        if source is not None and model_um_version is not None:
            source += f" vn{model_um_version}"

        # Only process the requested fields
        ok = True
        if select:
            values1 = (
                f"stash_code={stash}",
                f"lbproc={LBPROC}",
                f"lbtim={LBTIM}",
                f"runid={self.decode_lbexp()}",
                f"submodel={submodel}",
            )
            if um_stash_source is not None:
                values1 += (f"um_stash_source={um_stash_source}",)
            if source:
                values1 += (f"source={source}",)

            ok = False
            for value0 in select:
                for value1 in values1:
                    ok = Constructs._matching_values(
                        value0, None, value1, basic=True
                    )
                    if ok:
                        break

                if ok:
                    break

        if not ok:
            # This PP/UM field does not match the requested selection
            self.field = (None,)
            return

        # Still here?
        self._lbnpt = LBNPT
        self._lbrow = LBROW
        self._lbtim = LBTIM
        self._lbproc = LBPROC
        self._lbvc = LBVC
        self._bplat = BPLAT
        self._bplon = BPLON
        self._bdx = BDX
        self._bdy = BDY

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

        self._iz = _lbvc_to_axiscode.setdefault(LBVC, None)

        # Set _it from the calendar type
        if self._iy in (20, 23) or self._ix in (20, 23):
            # Time is dealt with by x or y
            self._it = None
        elif calendar == "gregorian":
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
                if not self.test_um_condition(
                    um_condition, LBCODE, BPLAT, BPLON
                ):
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

        # Set the data variable name
        self.name = self.add_to_variables(identity)
            
        if long_name is None:
            cf_properties["long_name"] = identity

        # Unique headers for the 'Z' axis
        recs = self._recs
        self._nz = nz
        self._z_recs = recs[:nz]
        self._t_recs = recs[::nz]
        
        self._axis = {}
        
        LBUSER5 = recs[0].int_hdr.item(lbuser5)
        
        self._z_axis = "z"
        
        cf_properties["Conventions"] = __Conventions__
        cf_properties["runid"] = self.decode_lbexp()
        cf_properties["lbproc"] = str(LBPROC)
        cf_properties["lbtim"] = str(LBTIM)
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
            
        # --------------------------------------------------------
        # Insert attributes and CF properties into the field
        # --------------------------------------------------------
        fill_value = data.fill_value
        if fill_value is not None:
            cf_properties["_FillValue"] = data.fill_value # TODO
             
        self.attrs.update(cf_properties)
        
        # --------------------------------------------------------
        # Get the extra data for this group
        # --------------------------------------------------------
        extra = recs[0].get_extra_data()
        self.extra = extra
        
        # --------------------------------------------------------
        # Create the 'T' dimension coordinate
        # --------------------------------------------------------
        axiscode = self._it
        if axiscode is not None:
            c = self.time_coordinate(axiscode)
            
        # --------------------------------------------------------
        # Create the 'Z' dimension coordinate
        # --------------------------------------------------------
        axiscode = self._iz
        if axiscode is not None:
            # Get 'Z' coordinate from LBVC
            if axiscode == 3:
                c = self.atmosphere_hybrid_sigma_pressure_coordinate(
                    axiscode
                )
            elif axiscode == 2 and "height" in self._cf_info:
                # Create the height coordinate from the information
                # given in the STASH to standard_name conversion table
                height, units = self.cf_info["height"]
                c = self.size_1_height_coordinate(axiscode, height, units)
            elif axiscode == 14:
                c = self.atmosphere_hybrid_height_coordinate(axiscode)
            else:
                c = self.z_coordinate(axiscode)

            # Create a model_level_number auxiliary coordinate
            LBLEV = int_hdr[INDEX_LBLEV]
            if LBVC in (2, 9, 65) or LBLEV in (7777, 8888):  # CHECK!
                self._lblev = LBLEV
                c = self.model_level_number_coordinate(aux=bool(c))

        # --------------------------------------------------------
        # Create the 'Y' dimension coordinate
        # --------------------------------------------------------
        axiscode = self._iy
        if axiscode is not None:
            if axiscode in (20, 23):
                # 'Y' axis is time-since-reference-date
                if extra.get("y", None) is not None:
                    c = self.time_coordinate_from_extra_data(axiscode, "y")
                else:
                    LBUSER3 = int_hdr[INDEX_LBUSER3]
                    self._lbuser3 = LBUSER3
                    if LBUSER3 == LBROW:
                        self._lbuser3 = LBUSER3
                        c = self.time_coordinate_from_um_timeseries(
                            axiscode, "y"
                        )
            else:
                yaxis = self.xy_coordinate(axiscode, "y")
                if axiscode == 13:
                    self._axis["site_axis"] = yaxis
                    self.site_coordinates_from_extra_data()

        # --------------------------------------------------------
        # Create the 'X' dimension coordinate
        # --------------------------------------------------------
        axiscode = self._ix
        if axiscode is not None:
            if axiscode in (20, 23):
                # X axis is time since reference date
                if extra.get("x", None) is not None:
                    c = self.time_coordinate_from_extra_data(axiscode, "x")
                else:
                    LBUSER3 = int_hdr[INDEX_LBUSER3]
                    self._lbuser3 = LBUSER3
                    if LBUSER3 == LBNPT:
                        self._lbuser3 = LBUSER3
                        c = self.time_coordinate_from_um_timeseries(
                            axiscode, "x"
                        )
            else:
                xaxis = self.xy_coordinate(axiscode, "x")
                if axiscode == 13:
                    self._axis["site_axis"] = xaxis
                    self.site_coordinates_from_extra_data()

        # -10: rotated latitude  (not an official axis code)
        # -11: rotated longitude (not an official axis code)

        if set((self._iy, self._ix)) == set((-10, -11)):
            # ----------------------------------------------------
            # Create a ROTATED_LATITUDE_LONGITUDE grid_mapping
            # variable
            # ----------------------------------------------------
            gm = _AuxVar(
                name="rotated_latitude_longitude",
                data=np.array("", dtype='S1')
                attrs={
                    "grid_mapping_name": "rotated_latitude_longitude",
                    "grid_north_pole_latitude": BPLAT,
                    "grid_north_pole_longitude": BPLON
                }
            )
            gm_name = self.add_to_variables(gm)
            self.attrs['grid_mapping'] =  gm_name
            
        # --------------------------------------------------------
        # Create a RADIATION WAVELENGTH dimension coordinate
        # --------------------------------------------------------
        try:
            rwl, rwl_units = self._cf_info["below"]
        except (KeyError, TypeError):
            pass
        else:
            c = self.radiation_wavelength_coordinate(rwl, rwl_units)

            # Set LBUSER5 to zero so that it is not confused for a
            # pseudolevel
            LBUSER5 = 0

        # --------------------------------------------------------
        # Create a PSEUDOLEVEL dimension coordinate. This must be done
        # *after* the possible creation of a radiation wavelength
        # dimension coordinate.
        # --------------------------------------------------------
        if LBUSER5 != 0:
            self.pseudolevel_coordinate(LBUSER5)

        # --------------------------------------------------------
        # Create cell methods
        # --------------------------------------------------------
        self.create_cell_methods()

        # Set the axis names for in the data variable's attributes
        if data_variable_meta.z_first:
            axis_order = 'ptyx'
        else:
            axis_order = 'tzyx'
            
        dim_names = [self._axis[axis] for axis in axis_order]
        self.attrs["DIMENSION_LIST"] = tuple((ncdim,) for ncdim in dim_names)

    def _reorder_z_axis(self, indices, z_axis, pmaxes):
        """Reorder the Z axis `Rec` instances.

        :Parameters:

            indices: `list`
                Aggregation axis indices. See `create_data` for
                details.

            z_axis: `int`
                The identifier of the Z axis.

            pmaxes: sequence of `int`
                The aggregation axes, which include the Z axis.

        :Returns:

            `list`

        **Examples**

        >>> _reorder_z_axis([(0, <Rec A>), (1, <Rec B>)], 0, [0])
        [(0, <Rec B>), (1, <Rec A>)]

        >>> _reorder_z_axis(
        ...     [(0, 0, <Rec A>),
        ...      (0, 1, <Rec B>),
        ...      (1, 0, <Rec C>),
        ...      (1, 1, <Rec D>)],
        ...     1, [0, 1]
        ... )
        [(0, 0, <Rec B>), (0, 1, <Rec A>), (1, 0, <Rec D>), (1, 1, <Rec C>)]

        """
        indices_new = []
        zpos = pmaxes.index(z_axis)
        aaa0 = indices[0]
        indices2 = [aaa0]
        for aaa in indices[1:]:
            if aaa[zpos] > aaa0[zpos]:
                indices2.append(aaa)
            else:
                indices_new.extend(indices2[::-1])
                aaa0 = aaa
                indices2 = [aaa0]

        indices_new.extend(indices2[::-1])

        indices = [a[:-1] + b[-1:] for a, b in zip(indices, indices_new)]
        return indices

    def atmosphere_hybrid_height_coordinate(self, axiscode):
        """`atmosphere_hybrid_height_coordinate` when not an array axis.

        **From appendix A of UMDP F3**

        From UM Version 5.2, the method of defining the model levels in PP
        headers was revised. At vn5.0 and 5.1, eta values were used in the
        PP headers to specify the levels of model data, which was of
        limited use when plotting data on model levels. From 5.2, the PP
        headers were redefined to give information on the height of the
        level. Given a 2D orography field, the height field for a given
        level can then be derived. The height coordinates for PP-output
        are defined as:

          Z(i,j,k)=Zsea(k)+C(k)*orography(i,j)

        where Zsea(k) and C(k) are height based hybrid coefficients.

          Zsea(k) = eta_value(k)*Height_at_top_of_model

          C(k)=[1-eta_value(k)/eta_value(first_constant_rho_level)]**2 for
               levels less than or equal to first_constant_rho_level
          C(k)=0.0 for levels greater than first_constant_rho_level

        where eta_value(k) is the eta_value for theta or rho level k. The
        eta_value is a terrain-following height coordinate; full details
        are given in UMDP15, Appendix B.

        The PP headers store Zsea and C as follows :-

          * 46 = bulev = brsvd1  = Zsea of upper layer boundary
          * 47 = bhulev = brsvd2 = C of upper layer boundary
          * 52 = blev            = Zsea of level
          * 53 = brlev           = Zsea of lower layer boundary
          * 54 = bhlev           = C of level
          * 55 = bhrlev          = C of lower layer boundary

        :Parameters:

            axiscode: `int`

        :Returns:

            `DimensionCoordinate` or `None`

        """
        z_recs = self._z_recs

        array = tuple(rec.real_hdr[INDEX_BLEV] for rec in z_recs) # Zsea
        
        bounds0_a = tuple(rec.real_hdr[INDEX_BRLEV] for rec in z_recs),  # Zsea lower            
        bounds1_a = tuple(rec.real_hdr[INDEX_BRSVD1] for rec in z_recs)  # Zsea upper

        array_b = tuple(rec.real_hdr[INDEX_BHLEV] for rec in z_recs)
        bounds0_b = tuple(rec.real_hdr[INDEX_BHRLEV] for rec in z_recs)
        bounds1_b = tuple(rec.real_hdr[INDEX_BRSVD2] for rec in z_recs)

        key = (
            'atmosphere_hybrid_height_coordinate'
            'BLEV', array_a,
            'BRLEV', bounds0_a, 
            'BRSVD1', bounds1_a, 
            'BHLEV', array_b,
            'BHRLEV', bounds0_b, 
            'BRSVD2', bounds1_b, 
        )
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            # Height at top of atmosphere
            toa_height = self._height_at_top_of_model
            if toa_height is None:
                pseudolevels = any(
                    [rec.int_hdr.item(lbuser5,) for rec in z_recs]
                )
                if pseudolevels:
                    # Pseudolevels and atmosphere hybrid height
                    # coordinates are both present => can't reliably infer
                    # height. This is due to a current limitation in the C
                    # library that means it can only create Z-T
                    # aggregations, rather than the required Z-T-P
                    # aggregations.
                    toa_height = -1
    
            if toa_height is None:
                toa_height = bounds1.max()
                if toa_height <= 0:
                    toa_height = None
            elif toa_height <= 0:
                toa_height = None
            else:
                toa_height = float(toa_height)

            real_dtype = self._real_hdr_dtype
                
            array_a = np.array(array_a,  dtype=real_dtype)
            bounds0_a = np.array(bounds0_a, dtype=real_dtype)
            bounds1_a = np.array(bounds1_a, dtype=real_dtype)
            bounds_a = self.create_bounds_array(bounds0_a, bounds1_a)
            
            array_b = np.array(array_b,  dtype=real_dtype)
            bounds0_b = np.array(bounds0_b, dtype=real_dtype)
            bounds1_b = np.array(bounds1_b, dtype=real_dtype)
            bounds_b = self.create_bounds_array(bounds0_b, bounds1_b)
       
            # atmosphere_hybrid_height_coordinate dimension coordinate
            if toa_height is None:
                d = _DimensionScale(
                    name="atmosphere_hybrid_height_coordinate",
                    size=array_a.size,
                    file_obj=self._file_obj
                )
                dim_ncvar = self.add_to_variables(d, 'dimension')
                self._axis['z'] = dim_ncvar
            else:
                array = array_a / toa_height
                bounds = bounds_a / toa_height
                
                dc = _DimensionScale(
                    data=array, axiscode=axiscode, file_obj=self._file_obj
                )
                dim_ncvar = self.add_to_variables(dc, 'dimension_coordinate')
                self._axis['z'] = dim_ncvar
                
                bounds_dim = self.bounds_dim(bounds)            
                dc_bounds = _AuxVar(
                    name=f"{dim_ncvar}_bounds",
                    data=bounds,
                    DIMENSION_LIST=((self._axis["z"],), (bounds_dim,)))
                )
                bounds_ncvar = self.add_to_variables(dc_bounds)

                dc.setattr('bounds', dc_bounds.name)
                
            # "a" domain ancillary
            da_a = _AuxVar(
                name="atmosphere_hybrid_height_coordinate_a",
                data=array_a,
                attrs={"long_name": "height based hybrid coeffient a",
                       "units": "m"},
                DIMENSION=LIST=((self._axis["z"]),)
            )
            ncvar = self.add_to_variables(da_a)
            
            # TODO                
            da_a.setattr('bounds', da_a_bounds.name)
            
            # "a" domain ancillary bounds
            bounds_dim = self.bounds_dim(bounds) 
            da_a_bounds = _AuxVar(
                name=f"{da_a.name}_bounds",
                data=bounds_a,
                DIMENSION=LIST=((_axis["z"]), (bounds_dim,))
            )
            ncvar = self.add_to_variables(da_a_bounds)
    
            # "b" domain ancillary
            da_b = _AuxVar(
                name="atmosphere_hybrid_height_coordinate_b",
                data=array_b,
                attrs={"long_name": "height based hybrid coeffient b",
                       "units": "1"},
                DIMENSION=LIST=((self._axis["z"]),)
            )
            ncvar = self.add_to_variables(da_b)
            
            # "b" domain ancillary bounds
            bounds_dim = self.bounds_dim(bounds) 
            da_b_bounds = _AuxVar(
                name=f"{da_b.name}_bounds",
                data=bounds_b,
                DIMENSION=LIST=((self._axis["z"]), (bounds_dim,))
            )
            ncvar = self.add_to_variables(da_b_bounds)
    
            # TODO                
            da_b.setattr('bounds', da_b_bounds.name)
                
            # Set the 'forumla terms' attriubtes on the parent coordinate
            # and coordinate bounds variables
            dc.setattr('formula_terms',
                       f"a: {da_a.name} b: {da_b.name}")
            dc_bounds.setattr('formula_terms',
                              f"a: {da_a_bounds.name} b: {da_b_bounds.name}")

            self._cache[key] = dim_ncvar
            
        else:
            self._axis['z'] = dim_ncvar
            
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

        :Returns:

            `DimensionCoordinate`

        """
        items = tuple(self.header_bz(rec) for rec in self._z_recs)
        key = ('atmosphere_hybrid_sigma_pressure_coordinate', items)
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            array = []
            bounds = []
            ak_array = []
            ak_bounds = []
            bk_array = []
            bk_bounds = []        
            
            for BLEV, BRLEV, BHLEV, BHRLEV, BULEV, BHULEV in items:
                array.append(BLEV + BHLEV / _pstar)
                bounds.append(
                    [BRLEV + BHRLEV / _pstar, BULEV + BHULEV / _pstar]
                )
    
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
            dc = _DimensionScale(
                data=array, axiscode=axicode, file_obj=self._file_obj
            )
            dim_ncvar = self.add_to_variables(dc, 'dimension_coordinate')
            self._axis['z'] = dim_ncvar
    
            bounds_dim = self.bounds_dim(bounds)            
            dc_bounds = _AuxVar(
                name=f"{dim_ncvar}_bounds",
                data=bounds,
                DIMENSION_LIST=((self._axis["z"],), (bounds_dim,)))
            )
            bounds_ncvar = self.add_to_variables(dc_bounds)

            # TODO
            dc.setattr('bounds', dc_bounds.name)
                     
            # "a" domain ancillary     
            da_a = _AuxVar(
                name="atmosphere_hybrid_sigma_pressure_coordinate_ak",
                data=ak_array,
                attrs={"long_name": "atmosphere_hybrid_sigma_pressure_coordinate_ak",
                       "units": "Pa"},
                DIMENSION_LIST=((self._axis['z'],),)
            )
            da_a_ncvar = self.add_to_variables(da_a)
    
            # "a" domain ancillary bounds
            bounds_dim = self.bounds_dim(bounds) 
            da_a_bounds = _AuxVar(
                name=f"{da_a.name}_bounds",
                data=ak_bounds,
                DIMENSION=LIST=((self._axis["z"]), (bounds_dim,))
            )
            ncvar = self.add_to_variables(da_a_bounds)
    
            # TODO
            da_a.setattr('bounds', da_a_bounds.name)
                   
            # "b" domain ancillary
            da_b = _AuxVar(
                name="atmosphere_hybrid_sigma_pressure_coordinate_bk",
                data=bk_array,
                attrs={
                    "long_name": "atmosphere_hybrid_sigma_pressure_coordinate_bk",
                    "units": "1"
                },
                DIMENSION=LIST=((_axis["z"],),)
            )
            ncvar = self.add_to_variables(da_b)
            
            # "b" domain ancillary bounds
            bounds_dim = self.bounds_dim(bounds) 
            da_b_bounds = _AuxVar(
                name=f"{da_b.name}_bounds",
                data=bk_bounds,
                DIMENSION=LIST=((self._axis["z"]), (bounds_dim,))
            )
            ncvar = self.add_to_variables(da_b_bounds)
    
            # TODO
            da_b.setattr('bounds', da_b_bounds.name)
                
            # Set the 'forumla terms' attriubtes on the parent coordinate
            # and coordinate bounds variables
            dc.setattr('formula_terms',
                       f"a: {da_a.name} b: {da_b.name}")
            dc_bounds.setattr('formula_terms',
                              f"a: {da_a_bounds.name} b: {da_b_bounds.name}")
    
            self._cache[key] = dim_ncvar

        else:
            self._axis['z'] = dim_ncvar
    
        self.add_coordinates(dim_ncvar)
        return dim_ncvar

    def create_bounds_array(self, bounds0, bounds1):
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

        """
        bounds = np.empty((bounds0.size, 2), dtype=bounds0.dtype)
        bounds[:, 0] = bounds0
        bounds[:, 1] = bounds1
        return bounds

    def create_cell_methods(self):
        """Create the cell methods.

        **UMDP F3**

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

            `list` of `str`
               The cell methods.

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
        if "t" in self._axis:
            axis = self._axis['t']
        else:
            axis = "time"

        if LBTIM_IB == 0 or LBTIM_IB == 1:
            if axis == "t":
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

        if not cell_methods:
            return

        self.attrs['cell_methods'] = ' '.join(cell_methods)

    def ctime(self, rec):
        """Return elapsed time since the clock time of the given
        record."""
        calendar = self._calendar
        refunits = self._refunits
        
        LBVTIME = self.header_vtime(rec)
        LBDTIME = self.header_dtime(rec)

        key = (LBVTIME, LBDTIME, refunits, calendar)
        ctime = _cache_ctime.get(key)
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
        
        _cache_ctime[key] = ctime
        return ctime

    def header_vtime(self, rec):
        """Return the list [LBYR, LBMON, LBDAT, LBHR, LBMIN] for the
        given record.

        :Parameters:

            rec:

        :Returns:

            `list`

        **Examples**

        >>> u.header_vtime(rec)
        (1991, 1, 1, 0, 0)

        """
        return tuple(rec.int_hdr[INDEX_LBYR : INDEX_LBMIN + 1])

    def header_dtime(self, rec):
        """Return the list [LBYRD, LBMOND, LBDATD, LBHRD, LBMIND] for
        the given record.

        :Parameters:

            rec:

        :Returns:

            `list`

        **Examples**

        >>> u.header_dtime(rec)
        (1991, 2, 1, 0, 0)

        """
        return tuple(rec.int_hdr[INDEX_LBYRD : INDEX_LBMIND + 1])

    def header_bz(self, rec):
        """Return the list [BLEV, BRLEV, BHLEV, BHRLEV, BULEV, BHULEV]
        for the given record.

        :Parameters:

            rec:

        :Returns:

            `list`

        **Examples**

        >>> u.header_bz(rec)

        """
        real_hdr = rec.real_hdr
        return tuple(
            real_hdr[INDEX_BLEV : INDEX_BHRLEV + 1].tolist()
            + real_hdr[  # BLEV, BRLEV, BHLEV, BHRLEV
                INDEX_BRSVD1 : INDEX_BRSVD2 + 1
            ].tolist()  # BULEV, BHULEV
        )

    def decode_lbexp(self):
        """Decode the integer value of LBEXP in the PP header into a
        runid.

        If this value has already been decoded, then it will be returned
        from the cache, otherwise the value will be decoded and then added
        to the cache.

        :Returns:

            `str`
               A string derived from LBEXP. If LBEXP is a negative integer
               then that number is returned as a string.

        **Examples**

        >>> self.decode_lbexp()
        'aaa5u'
        >>> self.decode_lbexp()
        '-34'

        """
        LBEXP = self._int_hdr[INDEX_LBEXP]

        runid = _cache_runid.get(LBEXP, None)
        if runid is not None:
            # Return the cached decoding
            return runid

        if LBEXP < 0:
            runid = str(LBEXP)
        else:
            # Convert LBEXP to a binary string, filled out to 30 bits with
            # zeros
            bits = bin(LBEXP)
            bits = bits.lstrip("0b").zfill(30)

            # Step through 6 bits at a time, converting each 6 bit chunk into
            # a decimal integer, which is used as an index to the characters
            # lookup list.
            runid = []
            for i in range(0, 30, 6):
                index = int(bits[i : i + 6], 2)
                if index < _n_characters:
                    runid.append(_characters[index])

            runid = "".join(runid)

        _cache_runid[LBEXP] = runid
        return runid

    def dtime(self, rec):
        """Return the elapsed time since the data time of the given
        record.

        :Parameters:

            rec:

        :Returns:

            `float`

        **Examples**

        >>> u.dtime(rec)
        31.5

        """
        refunits = self._refunits
        calendar = self._calendar

        LBDTIME = self.header_dtime(rec)

        key = (LBDTIME, refunits, calendar)
        time = _cache_date2num.get(key)
        if time is not None:
            return time
        
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

    def model_level_number_coordinate(self, aux=False):
        """model_level_number dimension or auxiliary coordinate.

        :Parameters:

            aux: `bool`

        :Returns:

            out: `str` or `None`

        """
        array = tuple(rec.int_hdr.item(INDEX_LBLEV) for rec in self._z_recs)
        key = ('model_level_number_coordinate', aux, array)
        ncvar = self._cache.get(key)
        if ncvar is None:
            # Still here?
            array = np.array(array, dtype=self._int_hdr_dtype)
            if array.min() < 0:
                return
            
            # Still here?
            array = np.where(array==9999, 0, array)
            axiscode = 5
            
            if aux:
                ac = _AuxVar(
                    data=array,
                    axiscode=axiscode,
                    DIMESNION_LIST=((self._axis["z"],),)
                )
                ncvar = self.add_to_variables(ac, 'auxiliary_coordinate')
            else:
                dc = _DimensionScale(
                    data=array, axiscode=axiscode, file_obj=self._file_obj
                )
                ncvar = self.add_to_variables(dc, 'dimension_coordinate')
                        
            self._cache[key] = ncvar

        if not aux:
            self._axis["z"] = ncvar
            
        self.add_coordinates(ncvar)
        return ncvar

    def pseudolevel_coordinate(self, LBUSER5):
        """Create and return the pseudolevel coordinate."""
        if self._nz == 1:
            array = (LBUSER5,)
        else:
            # 'Z' aggregation has been done along the pseudolevel axis
            array = tuple(rec.int_hdr.item(lbuser5) for rec in self._z_recs)
            self._z_axis = "p"

        key = ('pseudolevel_coordinate', array)
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            # Create new pseudolevel coordinate
            axiscode = 40
            array = np.array(array, dtype=self._int_hdr_dtype)
            dc = _DimensionScale(
                data=array,
                axiscode=axiscode,
                file_obj=self._file_obj,
                attrs= {"long_name": "pseudolevel"}
            )
            dim_ncvar = self.add_to_variables(dc)
                            
            self._cache[key] = dim_ncvar
            
        self._axis["p"] = dim_ncvar
        
        self.add_coordinates(dim_ncvar)
        return dim_ncvar
        
    def radiation_wavelength_coordinate(self, rwl, rwl_units):
        """Creata and return the radiation wavelength coordinate."""
        key = ('radiation_wavelength_coordinate', rwl, rwl_units)
        aux_ncvar = self._cache.get(key)
        if aux_ncvar is None:
            # Create new radiation wavelength coordinate
            array = np.array(rwl, dtype=float)
            bounds = np.array((0.0, rwl), dtype=float)
            
            axiscode = -20 
            ac = _AuxVar(
                data=array,
                axiscode=axiscode,
                attrs={'units': rwl_units},
                DIMENSION_LIST=(),
            )
            aux_ncvar = self.add_to_variables(ac, 'auxiliary_coordinate')
            
            bounds_dim = self.bounds_dim(bounds)            
            ac_bounds = _AuxVar(
                name=f"{aux_ncvar}_bounds",
                data=bounds,
                DIMENSION_LIST=((bounds_dim,),)
            )
            bounds_ncvar = self.add_to_variables(ac_bounds)

            ac.setattrs('bounds', bounds_ncvar )
            
            self._cache[key] = aux_ncvar
                     
        self._axis["r"] = dim_ncvar
        
        self.add_coordinates(aux_ncvar)
        return aux_ncvar


    def size_1_height_coordinate(self, axiscode, height, units):
        """Create and return the size-one height coordinate."""
        # Create the height coordinate from the information given in the
        # STASH to standard_name conversion table
        key=('size_1_height_coordinate', axiscode, height, units)
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            array = np.array((height,), dtype=float)
            dc = _AuxVar(
                data=array, axiscode=axiscode, file_obj=self._file_obj,
                attrs={'units': units}
            )
            dim_ncvar = self.add_to_variables(dc, 'scalar_coordinate')

            self._cache[key] = dim_ncvar
        
        # Add the scalar coordinate variable to the 'coordinates'
        # attribute
        self._axis["z"] = dim_ncvar
        self.add_coordinate(dim_ncvar)
        return dim_ncvar

    def test_um_condition(self, um_condition, LBCODE, BPLAT, BPLON):
        """Return `True` if a field satisfies the condition specified
        for a STASH code to standard name conversion.

        :Parameters:

            um_condition: `str`

            LBCODE: `int`

            BPLAT: `float`

            BPLON: `float`

        :Returns:

            `bool`
                `True` if a field satisfies the condition specified,
                `False` otherwise.

        **Examples**

        >>> ok = u.test_um_condition('true_latitude_longitude', ...)

        """
        if um_condition == "true_latitude_longitude":
            if LBCODE in _true_latitude_longitude_lbcodes:
                return True

            # Check pole location in case of incorrect LBCODE
            atol = self._atol
            if (
                abs(BPLAT - 90.0) <= atol + cf_rtol() * 90.0
                and abs(BPLON) <= atol
            ):
                return True

        elif um_condition == "rotated_latitude_longitude":
            if LBCODE in _rotated_latitude_longitude_lbcodes:
                return True

            # Check pole location in case of incorrect LBCODE
            atol = self._atol
            if not (
                abs(BPLAT - 90.0) <= atol + self._rtol() * 90.0
                and abs(BPLON) <= atol
            ):
                return True

        else:
            raise ValueError(
                "Unknown UM condition in STASH code conversion table: "
                f"{um_condition!r}"
            )

        # Still here? Then the condition has not been satisfied.
        return

    def test_um_version(self, valid_from, valid_to, um_version):
        """Return `True` if the UM version applicable to this field is
        within the given range.

        If possible, the UM version is derived from the PP header and
        stored in the metadata object. Otherwise it is taken from the
        *um_version* parameter.

        :Parameters:

            valid_from: `int`, `float` or `None`

            valid_to: `int`, `float` or `None`

            um_version: `int` or `float`

        :Returns:

            `bool`
                `True` if the UM version applicable to this field
                construct is within the range, `False` otherwise.

        **Examples**

        >>> ok = u.test_um_version(401, 505, 1001)
        >>> ok = u.test_um_version(401, None, 606.3)
        >>> ok = u.test_um_version(None, 405, 401)

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

        :Returns:

            `DimensionCoordinate`

        """
        t_recs = self._t_recs
        key  = (
            't_coordinate',
            tuple(
                (self.header_vtime(rec), self.header_dtime(rec))
                for rec in t_recs
            ),
            self._refunits,
            self._calendar
        )
        
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            # Create new 'T' coordinate
            vtimes = np.array([self.vtime(rec) for rec in t_recs], dtype=float)
            dtimes = np.array([self.dtime(rec) for rec in t_recs], dtype=float)
    
            if np.isnan(vtimes.sum()) or np.isnan(dtimes.sum()):
                return  # ppp
    
            IB = self._lbtim_ib
    
            if IB <= 1 or vtimes.item(0) >= dtimes.item(0):
                array = vtimes
                bounds = None
                climatology = False
            elif IB == 3:
                # The field is a time mean from T1 to T2 for each year
                # from LBYR to LBYRD
                ctimes = np.array([self.ctime(rec) for rec in t_recs])
                array = 0.5 * (vtimes + ctimes)
                bounds = self.create_bounds_array(vtimes, dtimes)
                climatology = True
            else:
                array = 0.5 * (vtimes + dtimes)
                bounds = self.create_bounds_array(vtimes, dtimes)
                climatology = False
                
            dc = _DimensionScale(
                data=array, axiscode=axiscode, file_obj=self._file_obj
            )
            dim_ncvar = self.add_to_variables(dc, 'dimension_coordinate')
            self._axis["t"] = dim_ncvar
            
            if bounds is not None:
                bounds_dim = self.bounds_dim(bounds)            
                dc_bounds = _AuxVar(
                    name=f"{dim_ncvar}_bounds",
                    data=bounds,
                    DIMENSION_LIST=((self._axis["t"],), (bounds_dim,)))
                )
                bounds_ncvar = self.add_to_variables(dc_bounds)
                
                if climatology:                
                    dc.setattr('climatology', bounds_ncvar)
                else:
                    dc.setattr('bounds', bounds_ncvar)

            self._cache[key] = dim_ncvar

        else:
            self._axis["t"] = dim_ncvar
        
        self.add_coordinates(dim_ncvar)
        return dim_ncvar 

    def bounds_dim(bounds):
        size = bounds.shape[-1]
        b = _DimensionScale(
            name=f"bounds{size}", size=size, file_obj=self._file_obj
        )
        name = self.add_to_variables(b)
        return name
    
    def time_coordinate_from_extra_data(self, axiscode, axis):
        """Create the time coordinate from extra data and return it.

        :Returns:

            `DimensionCoordinate`

        """
        extra = self.extra

        array = extra[axis]
        bounds = extra.get(axis + "_bounds", None)

        calendar = self.calendar
        if calendar == "360_day":
            units = "days since 0-1-1"
        elif calendar == "gregorian":
            units = _Units["gregorian 1752-09-13"]
        elif calendar == "365_day":
            units = _Units["365_day 1752-09-13"]
        else:
            units = None

        # Create time domain axis.
        #
        # Note that `axis` might not be "t". For instance, it could be
        # "y" if the time coordinates are coming from extra data.
        da = self.implementation.initialise_DomainAxis(size=array.size)
        axisT = self.implementation.set_domain_axis(self.field, da, copy=False)
        self._axis[axis] = axisT

        dc = self.implementation.initialise_DimensionCoordinate()
        dc = self.coord_data(dc, array, bounds, units=units)
        dc = self.coord_axis(dc, axiscode)
        dc = self.coord_names(dc, axiscode)

        self.implementation.set_dimension_coordinate(
            self.field,
            dc,
            axes=(axisT,),
            copy=False,
            autocyclic=_autocyclic_false,
        )

        return dc

    def time_coordinate_from_um_timeseries(self, axiscode, axis):
        """Create the time coordinate from a timeseries field."""
        # This PP/FF field is a timeseries. The validity time is
        # taken to be the time for the first sample, the data time
        # for the last sample, with the others evenly between.
        rec = self._recs[0]
        vtime = self.vtime(rec)
        dtime = self.dtime(rec)

        size = self._lbuser3 - 1.0
        delta = (dtime - vtime) / size

        calendar = self._calendar
        if calendar == "360_day":
            units = "days since 0-1-1"
        elif calendar == "gregorian":
            units = "days since 1752-09-13"
        elif calendar == "365_day":
            units = "days since 1752-09-13"

        array = np.arange(vtime, vtime + delta * size, size, dtype=float)

        dc = _DimensionScale(
            data=array,
            axiscode=axiscode,
            file_obj=self.fle_obj
            attrs={'units': units, 'calendar': calendar}
        )
        dim_ncvar = self.add_to_variablesd(dc)

        self._axis[axis] = dim_ncvar        
        self.add_to_coordinates(dim_ncvar)
        return dim_ncvar

    def vtime(self, rec):
        """Return the elapsed time since the validity time of the given
        record.

        :Parameters:

            rec:

        :Returns:

            `float`

        **Examples**

        >>> u.vtime(rec)
        31.5

        """
        refunits = self._refunits
        calendar = self._calendar
        LBVTIME = self.header_vtime(rec)
        
        key = (LBVTIME, refunits, calendar)

        time = _cache_date2num.get(key)
        if time is not None:
            return time
        
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

        self._cache_date2num[key] = time
        return time

    #    def dddd(self):
    #        """TODO."""
    #        for axis_code, extra_type in zip((11, 10), ("x", "y")):
    #            coord_type = extra_type + "_domain_bounds"
    #
    #            if coord_type in p.extra:
    #                p.extra[coord_type]
    #                # Create, from extra data, an auxiliary coordinate
    #                # with 1) data and bounds, if the upper and lower
    #                # bounds have no missing values; or 2) data but no
    #                # bounds, if the upper bound has missing values
    #                # but the lower bound does not.
    #
    #                # Should be the axis which has axis_code 13
    #                file_position = ppfile.tell()
    #                bounds = p.extra[coord_type][...]
    #
    #                # Reset the file pointer after reading the extra
    #                # data into a numpy array
    #                ppfile.seek(file_position, os.SEEK_SET)
    #                data = None
    #                # dch also test in bmdi?:
    #                if np.any(bounds[..., 1] == _pp_rmdi):
    #                    # dch also test in bmdi?:
    #                    if not np.any(bounds[..., 0] == _pp_rmdi):
    #                        data = bounds[..., 0]
    #                    bounds = None
    #                else:
    #                    data = np.mean(bounds, axis=1)
    #
    #                if (data, bounds) != (None, None):
    #                    aux = "aux%(auxN)d" % locals()
    #                    auxN += 1  # Increment auxiliary number
    #
    #                    coord = _create_Coordinate(
    #                        domain,
    #                        aux,
    #                        axis_code,
    #                        p=p,
    #                        array=data,
    #                        aux=True,
    #                        bounds_array=bounds,
    #                        pubattr={"axis": None},
    #                        # DCH xdim? should be the axis which has axis_code 13:
    #                        dimensions=[xdim],
    #                    )
    #            else:
    #                coord_type = "{0}_domain_lower_bound".format(extra_type)
    #                if coord_type in p.extra:
    #                    # Create, from extra data, an auxiliary
    #                    # coordinate with data but no bounds, if the
    #                    # data noes not contain any missing values
    #                    file_position = ppfile.tell()
    #                    data = p.extra[coord_type][...]
    #                    # Reset the file pointer after reading the
    #                    # extra data into a numpy array
    #                    ppfile.seek(file_position, os.SEEK_SET)
    #                    if not np.any(data == _pp_rmdi):  # dch + test in bmdi
    #                        aux = "aux%(auxN)d" % locals()
    #                        auxN += 1  # Increment auxiliary number
    #                        coord = _create_Coordinate(
    #                            domain,
    #                            aux,
    #                            axis_code,
    #                            p=p,
    #                            aux=True,
    #                            array=np.array(data),
    #                            pubattr={"axis": None},
    #                            dimensions=[xdim],
    #                        )  # DCH xdim?

    def add_to_coordinates(self, ncvar):
        attrs = self.attrs
        coordinates = attrs.get('coordinates', '')
        if coordinates:
            coordinates += f" {ncvar}"
        else:
            coordinates = ncvar

        attrs['coordinates'] = coordinates

    def add_to_variables(name, default='variable'):
        """TODO"""
        if not isinstance(name, (str, None)):
            var = name
            name = var.name
        else:
            var = None
            
        if name is None:
            name = default

        counter = 0
        unique_name = name
        while add_to_variables in self.variables:
            unique_name=f"{name}_{counter}"
            counter += 1

        if var is not None:
            var.name = unique_name
            
        self.variables[unique_name] = var            
        return unique_name

    def xy_coordinate(self, axiscode, axis):
        """Create an X or Y dimension coordinate from header entries or
        extra data.

        :Parameters:

            axiscode: `int`

            axis: `str`
                Which type of coordinate to create: ``'x'`` or
                ``'y'``.

        :Returns:

            (`str`, `DimensionCoordinate`)

        """
        if axis == "x":
            delta = self._bdx
            origin = self._real_hdr[INDEX_BZX]
            size = self._lbnpt
        else:
            delta = self._bdy
            origin = self._real_hdr[INDEX_BZY]
            size = self._lbrow

        key = (f"{axis}_coordinate", delta, origin, size)
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is None:
            if abs(delta) > self._atol:
                # Create regular coordinates from header items
                if axiscode == 11 or axiscode == -11:
                    origin -= divmod(origin + delta * size, 360.0)[0] * 360
                    while origin + delta * size > 360.0:
                        origin -= 360.0
                    while origin + delta * size < -360.0:
                        origin += 360.0
    
                array = _cached_regular_array.get((origin, delta, size))
                if array is None:
                    array = np.arange(
                        origin + delta,
                        origin + delta * (size + 0.5),
                        delta,
                        dtype=float,
                    )
                    _cached_regular_array[(origin, delta, size)] = array
    
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
                    bounds = _cached_regular_bounds.get((origin, delta, size))
                    if bounds is None:
                        delta_by_2 = 0.5 * delta
                        bounds = self.create_bounds_array(
                            array - delta_by_2, array + delta_by_2
                        )
                        _cached_regular_bounds[(origin, delta, size)] = bounds
            else:
                # Create coordinate from extra data
                array = self.extra.get(axis, None)
                lower_bounds = self.extra.get(axis + "_lower_bound", None)
                upper_bounds = self.extra.get(axis + "_upper_bound", None)
                if lower_bounds is not None and upper_bounds is not None:
                    bounds = self.create_bounds_array(
                        lower_bounds, upper_bounds
                    )
                else:
                    bounds = None
    
            dc = _DimensionScale(
                data=array, axiscode=axiscode, file_obj=self._file_obj
            )
            dim_ncvar = self.add_to_variables(dc)
            
            if bounds is not None:
                bounds_dim = self.bounds_dim(bounds)            
                dc_bounds= _AuxVar(
                    data=f"{dim_ncvar}_bounds",
                    DIMENSION_LIST=((self._axis[axis],), (bounds_dim,)))
                )
                bounds_ncvar = self.add_to_variables(dc_bounds)

                # TODO
                dc.setattr('bounds', bounds_ncvar)
            
        self.add_to_coordinates(ncvar)
        self._axis[axis] = dim_ncvar
        return dim_ncvar

    def site_coordinates_from_extra_data(self):
        """Create site-related coordinates from extra data.

        :Returns:

            `None`

        """
        # Create coordinate from extra data
        for axis, standard_name, units in zip(
            ("x", "y"),
            ("longitude", "latitude"),
            (_Units["degrees_east"], _Units["degrees_north"]),
        ):
            lower_bounds = self.extra.get(axis + "_domain_lower_bound", None)
            upper_bounds = self.extra.get(axis + "_domain_upper_bound", None)
            if lower_bounds is None or upper_bounds is None:
                continue

            # Still here?
            bounds = self.create_bounds_array(lower_bounds, upper_bounds)
            array = np.average(bounds, axis=1)

            ac = self.implementation.initialise_AuxiliaryCoordinate()
            ac = self.coord_data(ac, array, bounds, units=units)

            ac.standard_name = standard_name
            ac.long_name = "region limit"
            self.implementation.set_auxiliary_coordinate(
                self.field,
                ac,
                axes=[_axis["site_axis"]],
                copy=False,
                autocyclic=_autocyclic_false,
            )

        array = self.extra.get("domain_title", None)
        if array is not None:
            ac = self.implementation.initialise_AuxiliaryCoordinate()
            ac = self.coord_data(ac, array, None, units=None)

            ac.standard_name = "region"
            self.implementation.set_auxiliary_coordinate(
                self.field,
                ac,
                axes=[_axis["site_axis"]],
                copy=False,
                autocyclic=_autocyclic_false,
            )

    def z_coordinate(self, axiscode):
        """Create a Z dimension coordinate from BLEV.

        :Parameters:

            axiscode: `int`

        :Returns:

            `DimensionCoordinate`

        """
        z_recs = self._z_recs
        
        array = tuple(rec.real_hdr.item(INDEX_BLEV,) for rec in z_recs)
        bounds0 = tuple(rec.real_hdr.item(INDEX_BRLEV,) for rec in z_recs) # lower level boundary
        bounds1 = tuple(rec.real_hdr.item(INDEX_BRSVD1,) for rec in z_recs)  # bulev

        key  = tuple(
            'z_coordinate',
            'BLEV', array,
            'BRLEV', bounds0,
            'BRSVD1', bounds1
        )
        dim_ncvar = self._cache.get(key)
        if dim_ncvar is not None:
            self._axis["z"] = dim_ncvar
            return dim_ncvar
        
        if _coord_positive.get(axiscode, None) == "down":
            bounds0, bounds1 = bounds1, bounds0

        real_dtype = self._real_hdr_dtype
        array = np.array(array, dtype=real_dtype)
        bounds0 = np.array(bounds0, dtype=real_dtype)
        bounds1 = np.array(bounds1, dtype=real_dtype)
        bounds = self.create_bounds_array(bounds0, bounds1)

        if (bounds0 == bounds1).all() or np.allclose(bounds.min(), _pp_rmdi):
            bounds = None
        else:
            bounds = self.create_bounds_array(bounds0, bounds1)

        dc = _DimensionScale(
            data=array, axiscode=axiscode, file_obj=self._file_obj
        )
        dim_ncvar = self.add_to_variables(dc, 'dimension_coordinate')

        self._axis["z"] = dim_ncvar

        if bounds is not None:
            bounds_dim = self.bounds_dim(bounds)            
            b = _AuxVar(
                name=f"{dim_ncvar}_bounds",
                data=bounds,
                DIMENSION_LIST=((self._axis["z"],), (bounds_dim,)))
            )
            bounds_ncvar = self.add_to_variables(b)

            # Set the 'bounds' attribute on the parent corodiante
            # variable
            dc.setattr('bounds', bounds_ncvar)
        
        self._cache[key] = dim_ncvar
        return dim_ncvar
