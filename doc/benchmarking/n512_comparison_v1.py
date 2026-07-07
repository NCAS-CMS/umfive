import logging

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
)

import time

import cf

import umfive

EXAMPLE_FILE = "/Volumes/Lawrence4TB/xjanpa.pa19910301"
# EXAMPLE_FILE = str(Path.home()/"data/xjanpa.pa19910301")


def timecf(path):
    t0 = time.perf_counter()
    r = cf.read(path, dask_chunks=None)
    return time.perf_counter() - t0, r


def timep5(path):
    t0 = time.perf_counter()
    with umfive.File(path) as f:
        f.set_parallelism(thread_count=4)
        r = cf.read(f, dask_chunks=None)
    return time.perf_counter() - t0, r


def compare(path):
    # Do an extra one to ensure that caching is not affecting the comparison.
    # it may well be in play, but it's fairer to have it in play for both.
    cf_time, cf_result = timecf(path)
    # ok, now we're doing it for real:
    cf_time, cf_result = timecf(path)
    p5_time, p5_result = timep5(path)
    cfdict = {f.identity(): f for f in cf_result}
    p5dict = {f.identity(): f for f in p5_result}
    print(cfdict.keys())
    print(p5dict.keys())
    if set(cfdict) != set(p5dict):
        print("CF Variable identities:", set(cfdict))
        print("P5 Variable identities:", set(p5dict))

    results = [("meta", cf_time, p5_time, "", "")]
    keys = sorted(cfdict.keys() & p5dict.keys())
    for k in keys:
        p0 = time.perf_counter()
        cfm = cfdict[k].array
        p1 = time.perf_counter()
        cfm = cfm.max()
        p1a = time.perf_counter()
        p5m = p5dict[k].array
        p2 = time.perf_counter()
        p5m = p5m.max()
        if cfm != p5m:
            raise ValueError(
                f"Variable {k} has different max values: CF={cfm} P5={p5m}"
            )
        results.append(
            (
                k,
                p1 - p0,
                p2 - p1a,
                p5dict[k].get_property("is_wgdos_packed"),
                str(p5dict[k].shape).strip(),
            )
        )
    for r in results:
        val = "Tru" if r[3] else "Fal"
        print(
            f"{r[0]:<26} CF: {r[1]:.2f}s, P5: {r[2]:.2f}s (WGD={val}, {r[4]})"
        )


if __name__ == "__main__":
    N_TRIALS = 8
    for i in range(N_TRIALS):
        compare(EXAMPLE_FILE)
