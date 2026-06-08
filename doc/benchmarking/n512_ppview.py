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


def iteration(parallelism, iteration_index, usehttp=False):
    if usehttp:
        fs = fsspec.filesystem("https")
        reader = FsspecReader(fs, HTTP)
        ff_ctx = ppfive.File(HTTP, reader=reader)
    else:
        ff_ctx = ppfive.File(EXAMPLE_FILE)

    with ff_ctx as ff:
        ff.set_parallelism(**parallelism)
        for y in ff:
            if y.startswith("m0"):
                variable = ff[y]
                try:
                    name = variable.attrs["standard_name"]
                except KeyError:
                    name = variable.attrs.get("long_name", "unknown")
                wgdos = bool(variable.attrs.get("is_wgdos_packed", False))

                p0 = time.perf_counter()
                x = variable.value
                p1 = time.perf_counter()
                var_elapsed = p1 - p0
                print("Doing ", y, "(", name, ")")
                print(y, f"{x.shape} {x.dtype}")
                print(
                    f"PERF_VAR {{'POSIX' if not usehttp else 'HTTPS'}} parallism={parallelism} iter={iteration_index} var={y} "
                    f"wgdos={'T' if wgdos else 'F'} seconds={var_elapsed:.6f}"
                )


def executor(parallelism, iteration_index, usehttp=False):
    print(
        f"\nStarting iteration {iteration_index} with parallelism: {parallelism}"
    )
    start_time = time.perf_counter()
    iteration(parallelism, iteration_index, usehttp=usehttp)
    elapsed_time = time.perf_counter() - start_time
    print(
        f"Total elapsed time for iteration {iteration_index}: {elapsed_time:.2f} seconds"
    )


if __name__ == "__main__":

    thread_options = [1, 2, 4, 8]
    cat_range_options = [True, False]
    iterations = 8

    # POSIX TESTS

    parallelism_options = [
        {"thread_count": t, "cat_range_allowed": False} for t in thread_options
    ]

    for parallelism in parallelism_options:
        print(f"\nTesting POSIX with parallelism: {parallelism}")
        results = []
        for i in range(iterations):
            executor(parallelism, i, usehttp=False)

        avg_time = sum(results) / len(results)
        print(
            f"Average elapsed time for parallelism {parallelism}: {avg_time:.2f} seconds"
        )

    parallelism_options = [
        {"thread_count": t, "cat_range_allowed": c}
        for t in thread_options
        for c in cat_range_options
    ]

    for parallelism in parallelism_options:
        print(f"\nTesting HTTPS with parallelism: {parallelism}")
        results = []
        for i in range(iterations):
            executor(parallelism, i, usehttp=True)

        avg_time = sum(results) / len(results)
        print(
            f"Average elapsed time for parallelism {parallelism}: {avg_time:.2f} seconds"
        )
