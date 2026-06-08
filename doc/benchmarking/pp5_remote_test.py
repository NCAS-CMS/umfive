import logging
import time
from pathlib import Path

import fsspec

import ppfive
from ppfive.io import FsspecReader

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
)

FILENAME = "xjanpa.pa19910301"
EXAMPLE_FILE = str(Path.home() / "data" / FILENAME)
HTTP = f"https://gws-access.jasmin.ac.uk/public/hiresgw/{FILENAME}.pp"
FS_BLOCK_SIZE = 2 * 1024 * 1024


def process(variable, cat_label, nthreads):
    try:
        name = variable.attrs["standard_name"]
    except KeyError:
        name = variable.attrs.get("long_name", "unknown")
    print("Doing ", name)
    wgdos = bool(variable.attrs.get("is_wgdos_packed", False))
    p0 = time.perf_counter()
    x = variable.value
    p1 = time.perf_counter()
    var_elapsed = p1 - p0
    print(name, f"{x.shape} {x.dtype}")
    print(
        f"PERF_VAR var={name} CR={cat_label} W={'T' if wgdos else 'F'} {var_elapsed:.6f}s"
    )


def iteration(iteration_index, cat_range_allowed, nthreads):
    """Run one iteration of remote file access test."""
    fs = fsspec.filesystem("https", block_size=FS_BLOCK_SIZE)
    reader = FsspecReader(fs, HTTP)
    ff_ctx = ppfive.File(HTTP, reader=reader)
    cat_label = "ON" if cat_range_allowed else "OFF"

    with ff_ctx as ff:
        ff.set_parallelism(
            thread_count=nthreads, cat_range_allowed=cat_range_allowed
        )
        # variables = [y for y in ff if y.startswith('m0')]
        variables = [
            "m01s05i205",
            "m01s05i250",
        ]
        for variable in variables:
            process(ff[variable], cat_label, nthreads)


if __name__ == "__main__":
    iterations = 4
    print("Testing remote HTTPS access")
    for nthreads, cat_range_allowed in [
        (4, True),
        (1, True),
        (1, False),
    ]:
        cat_label = "ON" if cat_range_allowed else "OFF"
        print(f"\nTesting cat_ranges: {cat_label}")
        results = []
        for i in range(iterations):
            start_time = time.perf_counter()
            iteration(i, cat_range_allowed, nthreads)
            elapsed_time = time.perf_counter() - start_time
            results.append(elapsed_time)
            print(f"Elapsed time ({cat_label}): {elapsed_time:.2f} seconds")

        avg_time = sum(results) / len(results)
        print(f"Average elapsed time ({cat_label}): {avg_time:.2f} seconds")
