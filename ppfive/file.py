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

logger = logging.getLogger(__name__)


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


class _Variable:
    def __init__(self, attrs, data):
        pass
    

class _DimensionScale:
    """Internal pyfive-like dimension-scale dataset for cfdm bridging."""

    def __init__(
        self,
        name: str | None = None,
            size: int | None = None,
        file_obj: "File",
        *,
        standard_name: str | None = None,
        units: str | None = None,
        axis: str | None = None,
        positive: str | None = None,
        calendar: str | None = None,
        data: np.ndarray | None = None,
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
        self.attrs = {
            "CLASS": b"DIMENSION_SCALE",
            "NAME": b"netCDF dimension coordinate variable",
            "_Netcdf4Dimid": 0,
        }
        if standard_name:
            self.attrs["standard_name"] = np.bytes_(standard_name)
            
        if units:
            self.attrs["units"] = np.bytes_(units)

        if axis:
            self.attrs["axis"] = np.bytes_(axis)

        if positive:
            self.attrs["positive"] = np.bytes_(positive)

        if calendar:
            self.attrs["calendar"] = np.bytes_(calendar)

    def setattr(name, value):
        if isinstance(value, str):
            value = np._bytes_(value)

        self.attrs[name] = value

    def __getitem__(self, key):
        if self._data is not None:
            return self._data[key]

        raise ValueError("TODO")

#        return np.arange(self.shape[0], dtype=self.dtype)[key]


class _ScalarVar:
    """Scalar (shape=()) variable for ancillary metadata such as grid_mapping."""

    def __init__(self, name: str, attrs: dict):
        self.name = name
        self.shape = ()
        self.dtype = np.dtype("S1")
        self.maxshape = ()
        self.chunks = None
        self.attrs = attrs

    def __getitem__(self, key):
        return b""


class _AuxVar:
    """2-D auxiliary coordinate variable (e.g. unrotated latitude/longitude)."""

    def __init__(self, name: str, data: np.ndarray, attrs: dict):
        self.name = name
        self._data = data
        self.shape = data.shape
        self.dtype = data.dtype
        self.maxshape = data.shape
        self.chunks = None
        self.attrs = attrs

    def __getitem__(self, key):
        return self._data[key]


_PI_OVER_180 = np.pi / 180.0
_ATOL = 1e-8

def _regular_axis_values(origin: float, delta: float, size: int, *, is_longitude: bool) -> np.ndarray:
    """Create regular coordinate values from UM origin/delta header entries."""
    size = int(size)
    if size <= 0:
        return np.array([], dtype=np.float64)

    if abs(delta) <= _ATOL:
        return np.arange(1, size + 1, dtype=np.float64)

    if is_longitude:
        origin -= divmod(origin + delta * size, 360.0)[0] * 360.0
        while origin + delta * size > 360.0:
            origin -= 360.0
        while origin + delta * size < -360.0:
            origin += 360.0

    return np.arange(
        origin + delta,
        origin + delta * (size + 0.5),
        delta,
        dtype=np.float64,
    )


def _xy_axis_codes(lbcode: int) -> tuple[int | None, int | None]:
    """Return UM axis codes (ix, iy) inferred from LBCODE."""
    if lbcode in (1, 2):
        return 11, 10
    if lbcode in (101, 102):
        return -11, -10
    if lbcode >= 10000:
        x, y = divmod(divmod(lbcode, 10000)[1], 100)
        return x, y
    return None, None


def _derive_cell_methods(attrs: Mapping[str, Any], dim_names: tuple[str, ...]) -> str | None:
    """Derive CF cell_methods from UM LBPROC/LBTIM metadata (umread parity)."""
    methods: list[str] = []

    lbproc = int(attrs.get("lbproc", 0) or 0)
    lbtim = int(attrs.get("lbtim", 0) or 0)
    lbcode = int(attrs.get("lbcode", 0) or 0)
    cf_info = attrs.get("cf_info") or {}

    _, ib_ic = divmod(lbtim, 100)
    lbtim_ib, _ = divmod(ib_ic, 10)
    tmean_proc = 0

    # Ensemble mean.
    if 131072 <= lbproc < 262144:
        methods.append("realization: mean")
        lbproc -= 131072

    if lbtim_ib in (2, 3) and lbproc in (128, 192, 2176, 4224, 8320):
        tmean_proc = 128
        lbproc -= 128

    ix, iy = _xy_axis_codes(lbcode)

    # Area methods.
    if ix in (10, 11, 12, -10, -11) and iy in (10, 11, 12, -10, -11):
        if "where" in cf_info:
            methods.append("area: mean")
            methods.append(str(cf_info["where"]))
            if "over" in cf_info:
                methods.append(str(cf_info["over"]))

        if lbproc == 64:
            methods.append("x: mean")

    # Vertical methods.
    if lbproc == 2048:
        methods.append("z: mean")

    # Time methods.
    has_time_axis = "time" in dim_names
    axis = "time"
    if lbtim_ib in (0, 1):
        if has_time_axis:
            methods.append(f"{axis}: point")
    elif lbproc == 4096:
        methods.append(f"{axis}: minimum")
    elif lbproc == 8192:
        methods.append(f"{axis}: maximum")

    if tmean_proc == 128:
        if lbtim_ib == 2:
            methods.append(f"{axis}: mean")
        elif lbtim_ib == 3:
            methods.append(f"{axis}: mean within years")
            methods.append(f"{axis}: mean over years")

    if not methods:
        return None

    return " ".join(methods)


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
                    f"No valid records found in {self.fmt} file {self.filename}. "
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


            
        print ('variable_index=', variable_index)
        self._variable_index = variable_index
        self._variables = self._build_variables(variable_index or {})
        print ('self._variables=', self._variables)
        self.variables = self._variables
#        self._refresh_variable_views()

    def _refresh_variable_views(self) -> None:
        all_variables: dict[str, Any] = {}
        all_variables.update(self._variables)
        all_variables.update(self._pyfive_dimension_scales)
        all_variables.update(self._grid_mapping_vars)
        self.variables = all_variables

    def _build_variables(self, variable_index: dict[str, dict[str, Any]]) -> dict[str, Variable]:
        _dim_axis_map: dict[str, str | None] = {
            "time": "T",
            "air_pressure": "Z",
            "model_level_number": "Z",
            "pseudo_level": None,
            "grid_latitude": "Y",
            "grid_longitude": "X",
        }
        _dim_positive_map: dict[str, str] = {
            "air_pressure": "down",
        }

        def _vertical_dim_name(lbvc: int) -> str:
            if lbvc == 8:
                return "air_pressure"
            return "model_level_number"

        def _semantic_dim_names(shape: tuple[int, ...], attrs: Mapping[str, Any]) -> tuple[str, ...]:
            if len(shape) != 4:
                return tuple(f"dim_{axis}_{size}" for axis, size in enumerate(shape))

            lbvc = int(attrs.get("lbvc", 0) or 0)
            lbuser5 = int(attrs.get("lbuser5", 0) or 0)
            has_pseudo = lbuser5 not in (0, INT_MISSING_DATA)
            z_name = "pseudo_level" if has_pseudo else _vertical_dim_name(lbvc)

            # Mirrors build_variable_index ordering for pseudo-level fields.
            z_first = has_pseudo and shape[0] > 1 and shape[1] > 1
            if z_first:
                return (z_name, "time", "grid_latitude", "grid_longitude")

            return ("time", z_name, "grid_latitude", "grid_longitude")

        def _dim_units(name: str) -> str | None:
            if name == "air_pressure":
                return "Pa"
            if name in ("grid_latitude", "grid_longitude"):
                return "degrees"
            return None

        def _dim_standard_name(name: str) -> str | None:
            if name.startswith("dim_"):
                return None
            return name

        def _resolve_dim_name(base_name: str, dim_size: int) -> str:
            existing = self._pyfive_dimension_scales.get(base_name)
            if existing is None:
                return base_name
            if existing.shape == (int(dim_size),):
                return base_name

            return f"{base_name}_{dim_size}"

        def _dim_data(
            dim_name: str,
            dim_size: int,
            shape: tuple[int, ...],
            dim_names: tuple[str, ...],
            attrs: Mapping[str, Any],
        ) -> np.ndarray | None:
            if dim_name == "time":
                values = attrs.get("time_values")
                if values is not None:
                    return np.asarray(values, dtype=np.float64)

            if len(shape) < 2:
                return None

            if dim_name == "grid_latitude" and len(dim_names) >= 2 and dim_names[-2] == dim_name:
                return _regular_axis_values(
                    origin=float(attrs.get("bzy", 0.0)),
                    delta=float(attrs.get("bdy", 1.0)),
                    size=dim_size,
                    is_longitude=False,
                )

            if dim_name == "grid_longitude" and len(dim_names) >= 1 and dim_names[-1] == dim_name:
                return _regular_axis_values(
                    origin=float(attrs.get("bzx", 0.0)),
                    delta=float(attrs.get("bdx", 1.0)),
                    size=dim_size,
                    is_longitude=True,
                )

            return None

        variables: dict[str, Variable] = {}
        for name, meta in variable_index.items():
            shape = tuple(meta.get("shape", ()))
            attrs = _PyfiveAttrs(dict(meta.get("attrs", {})))

            raw_dim_names = _semantic_dim_names(shape, attrs)
            dim_names = tuple(
                _resolve_dim_name(dim_name, dim_size)
                for dim_name, dim_size in zip(raw_dim_names, shape)
            )
            for dim_name, dim_size in zip(dim_names, shape):
                if dim_name not in self._pyfive_dimension_scales:
                    self._pyfive_dimension_scales[dim_name] = _DimensionScale(
                        dim_name,
                        dim_size,
                        self,
                        standard_name=(dim_name if "dim_" not in dim_name else None),
                        units=_dim_units(dim_name),
                        axis=_dim_axis_map.get(dim_name),
                        positive=_dim_positive_map.get(dim_name),
                        calendar=(attrs.get("time_calendar") if dim_name == "time" else None),
                        data=_dim_data(dim_name, dim_size, shape, dim_names, attrs),
                    )

                    if dim_name == "time":
                        _time_units = attrs.get("time_units")
                        if _time_units is not None:
                            self._pyfive_dimension_scales[dim_name].attrs["units"] = np.bytes_(
                                str(_time_units)
                            )

            if dim_names:
                # Mirrors the structure expected by cfdm's p5netcdf adapter.
                attrs.setdefault(
                    "DIMENSION_LIST",
                    tuple((dim_name,) for dim_name in dim_names),
                )

            cell_methods = _derive_cell_methods(attrs, dim_names)
            if cell_methods:
                attrs.setdefault("cell_methods", cell_methods)

            # Detect rotated lat/lon grid from BPLAT (non-trivial pole position).
            bplat = attrs.get("bplat")
            bplon = attrs.get("bplon")
            if bplat is not None and float(bplat) != 90.0:
                _bplat = float(bplat)
                _bplon = float(bplon)
                if "rotated_latitude_longitude" not in self._grid_mapping_vars:
                    self._grid_mapping_vars["rotated_latitude_longitude"] = _ScalarVar(
                        "rotated_latitude_longitude",
                        {
                            "grid_mapping_name": "rotated_latitude_longitude",
                            "grid_north_pole_latitude": np.array([_bplat]),
                            "grid_north_pole_longitude": np.array([_bplon]),
                        },
                    )
                # Build 2-D true lat/lon auxiliaries from rotated grid parameters.
                if "latitude" not in self._grid_mapping_vars and len(shape) >= 2:
                    ny, nx = shape[-2], shape[-1]
                    y_name = dim_names[-2] if len(dim_names) >= 2 else "grid_latitude"
                    x_name = dim_names[-1] if len(dim_names) >= 1 else "grid_longitude"
                    bzy = float(attrs.get("bzy", 0.0))
                    bdy = float(attrs.get("bdy", 1.0))
                    bzx = float(attrs.get("bzx", 0.0))
                    bdx = float(attrs.get("bdx", 1.0))
                    rot_lat = bzy + bdy * np.arange(1, ny + 1, dtype=float)
                    rot_lon = bzx + bdx * np.arange(1, nx + 1, dtype=float)
                    true_lat, true_lon = _unrotated_latlon(rot_lat, rot_lon, _bplat, _bplon)
                    dim_list_2d = ((y_name,), (x_name,))
                    self._grid_mapping_vars["latitude"] = _AuxVar(
                        "latitude",
                        true_lat.astype(np.float64),
                        {
                            "CLASS": b"AUXILIARY_COORDINATE",
                            "standard_name": "latitude",
                            "units": "degrees_north",
                            "DIMENSION_LIST": dim_list_2d,
                        },
                    )
                    self._grid_mapping_vars["longitude"] = _AuxVar(
                        "longitude",
                        true_lon.astype(np.float64),
                        {
                            "CLASS": b"AUXILIARY_COORDINATE",
                            "standard_name": "longitude",
                            "units": "degrees_east",
                            "DIMENSION_LIST": dim_list_2d,
                        },
                    )
                attrs["coordinates"] = "latitude longitude"
                attrs["grid_mapping"] = "rotated_latitude_longitude"
                del attrs["bplat"]
                del attrs["bplon"]
            # Remove grid geometry attrs that served their purpose.
            for _k in (
                "bzy",
                "bdy",
                "bzx",
                "bdx",
                "lbcode",
                "time_values",
                "time_units",
                "time_calendar",
            ):
                attrs.pop(_k, None)

            variables[name] = Variable(
                name=name,
                attrs=attrs,
                shape=shape,
                dtype=meta.get("dtype"),
                chunk_shape=meta.get("chunk_shape"),
                data_loader=meta.get("data_loader"),
                file=self,
                parent=self,
                chunk_records=list(meta.get("chunk_records", [])),
            )
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
