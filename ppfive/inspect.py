from __future__ import annotations

from pathlib import Path
from typing import Any

from .dataset import File


def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except BrokenPipeError:
        raise SystemExit(1)


def clean_types(dtype):
    kind = dtype.kind
    itemsize = dtype.itemsize
    if kind == "f":
        return f"float{itemsize * 8}"
    if kind == "i":
        return f"int{itemsize * 8}"
    if kind == "u":
        return f"uint{itemsize * 8}"
    if kind in ("S", "a"):
        return "char"
    return str(dtype)


def _display_name(name: str, attrs: dict[str, Any]) -> str:
    um_identity = attrs.get("um_identity")
    if isinstance(um_identity, str) and um_identity:
        return um_identity
    return name


def _collect_dimensions_from_root(root: File) -> dict[str, int]:
    dims: dict[str, int] = {}
    for name, obj in root.variables.items():
        if obj.attrs.get("CLASS") != b"DIMENSION_SCALE":
            continue
        shape = getattr(obj, "shape", ())
        if shape:
            dims[name] = int(shape[0])
    return dims


def _gather_dimensions(ds, real_dimensions: dict[str, int], phony_dims: dict[int, str]):
    dims: list[tuple[str, int]] = []
    shape = tuple(getattr(ds, "shape", ()))

    # Dimension scales are their own coordinate variable.
    if ds.attrs.get("CLASS") == b"DIMENSION_SCALE":
        if shape:
            return [(ds.name, int(shape[0]))]
        return []

    dim_list = ds.attrs.get("DIMENSION_LIST")
    if dim_list:
        dim_names = []
        for ref in dim_list:
            if isinstance(ref, (list, tuple)) and ref:
                dim_names.append(str(ref[0]))
            else:
                dim_names.append(str(ref))

        for axis, size in enumerate(shape):
            if axis < len(dim_names):
                dims.append((dim_names[axis], int(size)))
            elif int(size) in real_dimensions.values():
                found = next((k for k, v in real_dimensions.items() if v == int(size)), None)
                if found is not None:
                    dims.append((found, int(size)))
                else:
                    pname = phony_dims.setdefault(int(size), f"phony_dim_{len(phony_dims)}")
                    dims.append((pname, int(size)))
            else:
                pname = phony_dims.setdefault(int(size), f"phony_dim_{len(phony_dims)}")
                dims.append((pname, int(size)))
        return dims

    for size in shape:
        size = int(size)
        if size in real_dimensions.values():
            found = next((k for k, v in real_dimensions.items() if v == size), None)
            if found is not None:
                dims.append((found, size))
                continue

        pname = phony_dims.setdefault(size, f"phony_dim_{len(phony_dims)}")
        dims.append((pname, size))

    return dims


def _print_attrs(indent: str, var_name: str, attrs: dict[str, Any], omit: list[str]):
    for key, value in attrs.items():
        if key in omit:
            continue

        if isinstance(value, bytes):
            value = f'"{value.decode("utf-8")}"'
        elif isinstance(value, str):
            value = f'"{value}"'

        safe_print(f"{indent}                {var_name}:{key} = {value} ;")


def ppncdump(file_path, special: bool = False):
    del special
    filename = getattr(file_path, "full_name", None) or file_path
    filename = Path(str(filename)).name

    with File(file_path) as f:
        real_dimensions = _collect_dimensions_from_root(f)
        safe_print(f"File: {filename} {{")
        safe_print("dimensions:")
        for dim_name, size in real_dimensions.items():
            safe_print(f"        {dim_name} = {size};")

        safe_print("variables:")

        phony_dims: dict[int, str] = {}
        for name, ds in f.variables.items():
            var_name = _display_name(name, ds.attrs)
            dtype_str = clean_types(ds.dtype)
            dims = _gather_dimensions(ds, real_dimensions, phony_dims)
            dim_names = [d[0] for d in dims]
            dim_str = f"({', '.join(dim_names)})" if dim_names else ""
            safe_print(f"        {dtype_str} {var_name}{dim_str} ;")

            omit = [
                "CLASS",
                "NAME",
                "_Netcdf4Dimid",
                "REFERENCE_LIST",
                "DIMENSION_LIST",
                "DIMENSION_LABELS",
                "_Netcdf4Coordinates",
            ]
            _print_attrs("", var_name, ds.attrs, omit)

        if f.attrs:
            safe_print("// global attributes:")
            _print_attrs("", "", f.attrs, ["_NCProperties"])

        safe_print("}")
