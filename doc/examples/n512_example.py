from __future__ import annotations

import argparse
import json
import random
import statistics
import subprocess
import sys
import time

import ppfive
from ppfive.io.local import LocalPosixReader

SOURCE_FILE = "/Volumes/Lawrence4TB/xjanpa.pa19910301"
N_TRIALS = 1


def metadata_probe(
    path: str, disable_os_cache: bool
) -> tuple[float, list[tuple[str, tuple[int, ...], dict]]]:
    t0 = time.perf_counter()
    with ppfive.File(path, disable_os_cache=disable_os_cache) as f:
        rows = []
        for name in f:
            var = f[name]
            max = var[:].max()
            rows.append((name, var.shape, dict(var.attrs), max))
    return time.perf_counter() - t0, rows


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    rank = (len(values) - 1) * q
    low = int(rank)
    high = min(low + 1, len(values) - 1)
    frac = rank - low
    return values[low] * (1.0 - frac) + values[high] * frac


def run_worker(path: str, disable_os_cache: bool) -> float:
    cmd = [
        sys.executable,
        __file__,
        "--worker",
        "--source-file",
        path,
        "--disable-os-cache",
        "1" if disable_os_cache else "0",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(proc.stdout.strip())
    return float(payload["metadata_seconds"])


def print_variable_metadata(path: str, disable_os_cache: bool) -> None:
    _, rows = metadata_probe(path, disable_os_cache=disable_os_cache)
    print("\nVariables (metadata only):")
    for name, shape, attrs in rows:
        print(f"- {name}: shape={shape}")
        print(
            f"  is_packed={attrs.get('is_packed')} is_wgdos_packed={attrs.get('is_wgdos_packed')}"
        )
        print(
            f"  packing_modes={attrs.get('packing_modes')} compression_modes={attrs.get('compression_modes')}"
        )


def benchmark(path: str, trials: int, drop_cache_between_runs: bool) -> None:
    modes = [
        ("cache-on", False),
        ("cache-bypass-hint", True),
    ]
    results: dict[str, list[float]] = {name: [] for name, _ in modes}

    # Warm up worker startup path once per mode, but do not record.
    for _, disable in modes:
        run_worker(path, disable)

    drop_successes = 0
    drop_attempts = 0

    for _ in range(trials):
        order = modes[:]
        random.shuffle(order)
        for name, disable in order:
            if drop_cache_between_runs:
                drop_attempts += 1
                if LocalPosixReader.drop_os_cache_best_effort():
                    drop_successes += 1
            dt = run_worker(path, disable)
            results[name].append(dt)

    print("\n=== subprocess metadata benchmark ===")
    print(f"source_file={path}")
    print(f"trials_per_mode={trials}")
    print(f"drop_cache_between_runs={drop_cache_between_runs}")
    if drop_cache_between_runs:
        print(f"drop_cache_successes={drop_successes}/{drop_attempts}")

    for name, _ in modes:
        vals = sorted(results[name])
        print(f"\n{name}")
        print(f"runs: {', '.join(f'{v:.3f}s' for v in vals)}")
        print(
            "mean={:.3f}s median={:.3f}s p95={:.3f}s".format(
                statistics.mean(vals),
                statistics.median(vals),
                _percentile(vals, 0.95),
            )
        )

    print_variable_metadata(path, disable_os_cache=False)


def worker_mode(path: str, disable_os_cache: bool) -> None:
    dt, _ = metadata_probe(path, disable_os_cache=disable_os_cache)
    print(json.dumps({"metadata_seconds": dt}))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Metadata cache-on/off benchmark for ppfive"
    )
    parser.add_argument(
        "--worker", action="store_true", help="Run one worker measurement"
    )
    parser.add_argument("--source-file", default=SOURCE_FILE)
    parser.add_argument("--disable-os-cache", default="0", choices=["0", "1"])
    parser.add_argument("--trials", type=int, default=N_TRIALS)
    parser.add_argument("--drop-cache-between-runs", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.worker:
        worker_mode(
            args.source_file, disable_os_cache=(args.disable_os_cache == "1")
        )
    else:
        benchmark(
            args.source_file,
            trials=args.trials,
            drop_cache_between_runs=args.drop_cache_between_runs,
        )
