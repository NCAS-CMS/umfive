# ppfive

A PP and Fields file reader that mimics relevant parts of the `pyfive` high-level API,
with support for lazy metadata loading and parallel data loading when necessary.

This is NOT an alternative to pyfive, it is a package which makes pp and fields files
look like and taste ("quack like") chunked HDF5 files written by a NetCDF library.

## API Contract (ppfive vs pyfive)

`ppfive` is designed to be **pyfive-compatible** as far as likely users of pyfive
would need such compatability. That is, it produces a chunk index (for kerchunk)
if you really want that, and it supports all the information needed by CF/CFDM
workflows to make pp-data as CF-compliant as possible.


For the canonical pyfive interface, see the pyfive docs:

- https://pyfive.readthedocs.io/

### What maps directly to pyfive

- `ppfive.File` is registered as a `pyfive.File` virtual type (when `pyfive` is installed).
- `ppfive.Variable` is registered as a `pyfive.Dataset` virtual type.
- File/root-level members expected by pyfive-style callers are present:
	- `attrs`, `groups`, `variables`, `dimensions`, `name`, `path`, `parent`
- Mapping-style access works:
	- `f["var"]`, iteration over variables, `items()`, `len(f)`
- Dataset-like variable members needed by downstream consumers are present:
	- `shape`, `dtype`, `ndim`, `size`, `attrs`, `chunks`/`chunk_shape`, `file`, `parent`
	- slicing/indexing via `__getitem__` (for example `f["var"][:]`)
	- `read_direct`, `astype(...)`, `iter_chunks(...)`

Like pyfive, ppfive is Read-only:

	- `File(..., mode="r")` is supported; write/update modes are not.

### Important differences from pyfive


- No nested groups in PP/Fields model:
	- `f["group/var"]` is not supported.
	- `groups` exists for compatibility but is empty for current PP/Fields inputs.
- `get_lazy_view(...)` fallback behavior:
	- `pyfive`-style API entry exists, but returns the normal variable view with an info log.
- Some Dataset properties are intentionally placeholders (`None`) because they are
	not meaningful for PP/Fields records:
	- `compression`, `compression_opts`, `shuffle`, `fletcher32`, `maxshape`,
		`fillvalue`, `dims`, `scaleoffset`.
- Compatibility metadata is synthesized for CF/cfdm bridging:
	- dimension-scale datasets and `DIMENSION_LIST` are created where needed.
	- rotated-grid helper variables (for example `latitude`, `longitude`,
		`rotated_latitude_longitude`) may be exposed when implied by UM headers.
- ppfive-specific extension API:
	- `File.set_parallelism(thread_count=..., cat_range_allowed=...)`
		is provided by ppfive and is not part of `pyfive`.


### Practical expectation

If your code treats `ppfive.File` and `ppfive.Variable` as `pyfive`-like read objects,
common analysis workflows should work, including chunk-level access (pp records
are treated as chunks).  

## Authorship

Key authors of this package are:

- David Hassell (@davidhassell)
- Alan Iwi (@alaniwi)
- Bryan Lawrence (@bnlawrence)
