from pathlib import Path

import cf
import numpy as np
import pytest

from ppfive import File


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
EXCLUDED_SUFFIXES = {".nc", ".md"}
KNOWN_XFAILS = {}


def _data_variable_names(f: File) -> list[str]:
    return [
        name
        for name, variable in f.variables.items()
        if variable.attrs.get("CLASS")
        not in (b"DIMENSION_SCALE", b"AUXILIARY_COORDINATE")
        and "grid_mapping_name" not in variable.attrs
    ]


def _matches_cf_with_optional_z_flip(
    arr: np.ndarray, baseline: np.ndarray
) -> bool:
    squeezed = np.squeeze(arr)
    if squeezed.shape != baseline.shape:
        return False

    # Use dtype-scaled precision tolerance rather than a coarse absolute floor.
    # This keeps checks strict across both small and large-magnitude fields.
    if baseline.dtype.kind == "f":
        eps = np.finfo(baseline.dtype).eps
        rtol, atol = 32 * eps, 32 * eps
    else:
        rtol, atol = 1e-6, 1e-6

    if np.allclose(squeezed, baseline, rtol=rtol, atol=atol):
        return True

    if squeezed.ndim >= 2 and np.allclose(
        squeezed[:, ::-1, ...], baseline, rtol=rtol, atol=atol
    ):
        return True

    return False


def _fixture_params() -> list[object]:
    params = []
    for path in sorted(
        path
        for path in DATA_DIR.iterdir()
        if path.is_file() and path.suffix.lower() not in EXCLUDED_SUFFIXES
    ):
        if path.name in KNOWN_XFAILS:
            params.append(
                pytest.param(
                    path,
                    marks=pytest.mark.xfail(
                        reason=KNOWN_XFAILS[path.name], strict=True
                    ),
                    id=path.name,
                )
            )
        else:
            params.append(pytest.param(path, id=path.name))
    return params


@pytest.mark.parametrize("path", _fixture_params())
def test_real_um_file_data_parity_with_cf(path: Path):
    # Special case: corrupted file should raise ValueError
    if path.name == "dk922a.p41983apr":
        with pytest.raises(ValueError, match="No valid records found"):
            File(str(path))
        return

    with File(str(path)) as f:
        names = _data_variable_names(f)
        assert names, f"Expected at least one parsed variable in {path.name}"

        fields = cf.read(str(path))
        assert len(fields) == len(names), (
            f"Expected same number of variables/fields for {path.name}: "
            f"ppfive={len(names)} cf={len(fields)}"
        )

        for name, field in zip(names, fields):
            arr = f[name][:]
            baseline = np.asarray(field.array)

            assert baseline.shape == np.squeeze(arr).shape, (
                f"Shape mismatch for {path.name} variable {name}: "
                f"ppfive={arr.shape} cf={baseline.shape}"
            )
            assert baseline.dtype == arr.dtype, (
                f"Dtype mismatch for {path.name} variable {name}: "
                f"ppfive={arr.dtype} cf={baseline.dtype}"
            )
            assert _matches_cf_with_optional_z_flip(arr, baseline), (
                f"Data mismatch for {path.name} variable {name}"
            )
