import argparse
import gc
import logging
import statistics as st
import time
from pathlib import Path

import cf
import dask

import umfive

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
)

DEFAULT_PATH = "/Volumes/Lawrence4TB/xjanpa.pa19910301"


def _parse_dask_chunks(value: str):
    text = value.strip().lower()
    if text == "none":
        return None
    if text == "default":
        return "__DEFAULT__"
    if text == "single":
        return -1
    raise ValueError("dask-chunks must be one of: none, default, single")


def _read_cf(path: str, dask_chunks):
    if dask_chunks == "__DEFAULT__":
        return cf.read(path)
    return cf.read(path, dask_chunks=dask_chunks)


def _read_p5(path: str, dask_chunks, thread_count: int):
    with umfive.File(path) as f:
        f.set_parallelism(thread_count=thread_count)
        if dask_chunks == "__DEFAULT__":
            return cf.read(f)
        return cf.read(f, dask_chunks=dask_chunks)


def _time_field_arrays(
    fields, targets: set[str] | None, dask_scheduler: str | None
):
    timed = {}
    for field in fields:
        name = field.identity()
        if targets is not None and name not in targets:
            continue

        ctx = (
            dask.config.set(scheduler=dask_scheduler)
            if dask_scheduler
            else _null_ctx()
        )
        with ctx:
            t0 = time.perf_counter()
            arr = field.array
            t1 = time.perf_counter()

            t2 = time.perf_counter()
            _ = arr.max()
            t3 = time.perf_counter()

        timed[name] = {
            "array_sec": t1 - t0,
            "max_sec": t3 - t2,
            "shape": tuple(field.shape),
            "is_wgd": bool(field.get_property("is_wgdos_packed", False)),
        }
    return timed


class _null_ctx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def _run_one_mode(
    mode: str,
    path: str,
    dask_chunks,
    thread_count: int,
    targets: set[str] | None,
    dask_scheduler: str | None,
):
    if mode == "CF":
        fields = _read_cf(path, dask_chunks)
    elif mode == "P5":
        fields = _read_p5(path, dask_chunks, thread_count)
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    return _time_field_arrays(fields, targets, dask_scheduler)


def _summary(values: list[float]) -> str:
    if not values:
        return "n=0"
    return (
        f"n={len(values)} mean={st.mean(values):.4f}s "
        f"median={st.median(values):.4f}s min={min(values):.4f}s max={max(values):.4f}s"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tighter CF-vs-Umfive benchmark with warmup discard and alternating run order"
    )
    parser.add_argument(
        "--path", default=DEFAULT_PATH, help="Input PP/Fields file path"
    )
    parser.add_argument(
        "--trials", type=int, default=8, help="Number of measured trials"
    )
    parser.add_argument(
        "--warmup", type=int, default=2, help="Warmup trials to discard"
    )
    parser.add_argument(
        "--thread-count", type=int, default=4, help="Umfive local thread count"
    )
    parser.add_argument(
        "--dask-chunks",
        default="none",
        choices=["none", "default", "single"],
        help="CF dask chunk mode: none, default, or single (-1)",
    )
    parser.add_argument(
        "--targets",
        default="",
        help="Comma-separated field identities to benchmark; empty means all common fields",
    )
    parser.add_argument(
        "--dask-scheduler",
        default=None,
        choices=["synchronous", "threads", "processes"],
        help="Force dask scheduler for .array calls (default: dask's own default)",
    )
    args = parser.parse_args()

    if args.trials <= 0:
        raise ValueError("--trials must be > 0")
    if args.warmup < 0:
        raise ValueError("--warmup must be >= 0")
    if args.thread_count < 0:
        raise ValueError("--thread-count must be >= 0")

    dask_chunks = _parse_dask_chunks(args.dask_chunks)
    targets = {x.strip() for x in args.targets.split(",") if x.strip()} or None
    dask_scheduler = args.dask_scheduler

    print("CONFIG")
    print(f"  path={Path(args.path)}")
    print(f"  trials={args.trials} warmup={args.warmup}")
    print(
        f"  dask_chunks={args.dask_chunks} umfive_thread_count={args.thread_count}"
    )
    print(f"  dask_scheduler={dask_scheduler or 'default'}")
    print(f"  targets={'ALL_COMMON' if targets is None else sorted(targets)}")

    # Warmup runs (discarded), alternating order.
    for i in range(args.warmup):
        order = ("CF", "P5") if i % 2 == 0 else ("P5", "CF")
        print(f"WARMUP {i + 1}/{args.warmup} order={order}")
        for mode in order:
            _ = _run_one_mode(
                mode,
                args.path,
                dask_chunks,
                args.thread_count,
                targets,
                dask_scheduler,
            )
            gc.collect()

    stats = {}

    # Measured runs.
    for i in range(args.trials):
        order = ("CF", "P5") if i % 2 == 0 else ("P5", "CF")
        print(f"TRIAL {i + 1}/{args.trials} order={order}")

        trial_data = {}
        for mode in order:
            trial_data[mode] = _run_one_mode(
                mode,
                args.path,
                dask_chunks,
                args.thread_count,
                targets,
                dask_scheduler,
            )
            gc.collect()

        cf_data = trial_data["CF"]
        p5_data = trial_data["P5"]

        common = sorted(set(cf_data) & set(p5_data))
        if not common:
            print("No common variable identities in this trial")
            continue

        for name in common:
            cf_arr = cf_data[name]["array_sec"]
            p5_arr = p5_data[name]["array_sec"]
            wgd = p5_data[name]["is_wgd"]
            shape = str(p5_data[name]["shape"])

            print(
                f"{name:<26} CF: {cf_arr:.2f}s, P5: {p5_arr:.2f}s "
                f"(WGD={'Tru' if wgd else 'Fal'}, {shape})"
            )

            rec = stats.setdefault(
                name,
                {
                    "wgd": wgd,
                    "shape": shape,
                    "cf_array": [],
                    "p5_array": [],
                    "cf_max": [],
                    "p5_max": [],
                },
            )
            rec["cf_array"].append(cf_arr)
            rec["p5_array"].append(p5_arr)
            rec["cf_max"].append(cf_data[name]["max_sec"])
            rec["p5_max"].append(p5_data[name]["max_sec"])

    print("\nSUMMARY (array timing)")
    for name in sorted(stats):
        rec = stats[name]
        cf_vals = rec["cf_array"]
        p5_vals = rec["p5_array"]
        cf_med = st.median(cf_vals)
        p5_med = st.median(p5_vals)
        ratio = (p5_med / cf_med) if cf_med else float("inf")
        print(
            f"{name:<26} WGD={'Tru' if rec['wgd'] else 'Fal'} shape={rec['shape']} "
            f"CF[{_summary(cf_vals)}] P5[{_summary(p5_vals)}] median_ratio(P5/CF)={ratio:.3f}"
        )

    print("\nSUMMARY (max timing)")
    for name in sorted(stats):
        rec = stats[name]
        print(
            f"{name:<26} CFmax[{_summary(rec['cf_max'])}] P5max[{_summary(rec['p5_max'])}]"
        )


if __name__ == "__main__":
    main()
