from __future__ import annotations

import argparse
import math
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

PERF_VAR_RE = re.compile(
    r"PERF_VAR\s+thread=(?P<thread>\d+)\s+iter=(?P<iter>\d+)\s+"
    r"var=(?P<var>\S+)(?:\s+cat=(?P<cat>ON|OFF))?(?:\s+wgdos=(?P<wgdos>[TF]))?\s+"
    r"seconds=(?P<seconds>[0-9]*\.?[0-9]+)"
)
VAR_SHAPE_RE = re.compile(
    r"^(?P<var>m\d+s\d+i\d+(?:_\d+)?)\s+\((?P<shape>[^)]*)\)\s+\S+"
)
DOING_NAME_RE = re.compile(
    r"^Doing\s+(?P<var>m\d+s\d+i\d+(?:_\d+)?)\s+\(\s*(?P<name>.*?)\s*\)\s*$"
)


def parse_perf_var_lines(log_path: Path):
    """Return timing rows and variable metadata mapping from a ppview
    log."""
    rows: list[tuple[str, str, int, float]] = []
    metadata_by_var: dict[str, dict[str, str | bool]] = {}
    has_cat = False

    def _ensure_meta(var: str) -> dict[str, str | bool]:
        if var not in metadata_by_var:
            metadata_by_var[var] = {}
        return metadata_by_var[var]

    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()

            name_match = DOING_NAME_RE.search(stripped)
            if name_match is not None:
                var = name_match.group("var")
                meta = _ensure_meta(var)
                meta.setdefault("name", name_match.group("name"))

            shape_match = VAR_SHAPE_RE.search(stripped)
            if shape_match is not None:
                var = shape_match.group("var")
                meta = _ensure_meta(var)
                meta.setdefault("shape", shape_match.group("shape"))

            match = PERF_VAR_RE.search(stripped)
            if match is None:
                continue
            try:
                var = match.group("var")
                meta = _ensure_meta(var)
                cat = match.group("cat")
                wgdos = match.group("wgdos")
                if wgdos is not None:
                    meta["wgdos"] = wgdos == "T"

                if cat is not None:
                    has_cat = True
                    config_label = cat
                else:
                    config_label = match.group("thread")

                rows.append(
                    (
                        var,
                        config_label,
                        int(match.group("iter")),
                        float(match.group("seconds")),
                    )
                )
            except ValueError as exc:
                raise ValueError(
                    f"Failed to parse PERF_VAR on line {line_number}: {line.strip()}"
                ) from exc
    return rows, metadata_by_var, has_cat


def group_by_variable_config(rows: list[tuple[str, str, int, float]]):
    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for var, config_label, _iter_idx, seconds in rows:
        grouped[var][config_label].append(seconds)
    return grouped


def sort_config_labels(labels: list[str], has_cat: bool) -> list[str]:
    if has_cat:
        order = {"OFF": 0, "ON": 1}
        return sorted(labels, key=lambda item: order.get(item, 99))
    return sorted(
        labels, key=lambda item: int(item) if item.isdigit() else item
    )


def make_boxplots(
    grouped: dict[str, dict[str, list[float]]],
    metadata_by_var: dict[str, dict[str, str | bool]],
    has_cat: bool,
    output_path: Path,
    title: str | None = None,
):
    variables = sorted(grouped)
    if not variables:
        raise ValueError(
            "No PERF_VAR rows found. Re-run n512_ppview.py to regenerate the log with per-variable timings."
        )

    n = len(variables)
    ncols = 3
    nrows = math.ceil(n / ncols)
    fig, axes = plt.subplots(
        nrows=nrows,
        ncols=ncols,
        figsize=(5.2 * ncols, 2.8 * nrows),
        squeeze=False,
    )

    for i, var in enumerate(variables):
        ax = axes[i // ncols][i % ncols]
        by_config = grouped[var]
        config_labels = sort_config_labels(list(by_config), has_cat)
        data = [by_config[label] for label in config_labels]

        ax.boxplot(data, tick_labels=config_labels, showmeans=True)
        meta = metadata_by_var.get(var, {})
        name = str(meta.get("name", ""))
        shape = str(meta.get("shape", ""))
        wgdos = meta.get("wgdos")
        if isinstance(wgdos, bool):
            wgdos_text = "T" if wgdos else "F"
        else:
            wgdos_text = "?"

        title_line_1 = f"{var} ({name})" if name else var
        if shape:
            title_line_2 = f"({shape}, W={wgdos_text})"
        else:
            title_line_2 = f"(W={wgdos_text})"
        ax.set_title(f"{title_line_1}\n{title_line_2}")
        ax.set_xlabel("Cat ranges" if has_cat else "Thread count")
        ax.set_ylabel("Seconds")
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", alpha=0.25)

    total_axes = nrows * ncols
    for j in range(n, total_axes):
        axes[j // ncols][j % ncols].axis("off")

    fig_title = title or (
        "Per-variable timing by cat_ranges setting"
        if has_cat
        else "Per-variable timing by thread count"
    )
    fig.suptitle(fig_title)
    fig.tight_layout()
    fig.subplots_adjust(top=0.94)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Extract per-variable/thread timings from ppview log and plot boxplots."
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("doc/examples/ppview-posix-mac.log"),
        help="Path to ppview log file",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("doc/examples/ppview-variable-thread-boxplots.png"),
        help="Output plot image path",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Optional figure title",
    )

    args = parser.parse_args()
    rows, metadata_by_var, has_cat = parse_perf_var_lines(args.log)
    grouped = group_by_variable_config(rows)
    make_boxplots(
        grouped, metadata_by_var, has_cat, args.out, title=args.title
    )

    n_points = sum(
        len(v) for by_thread in grouped.values() for v in by_thread.values()
    )
    print(
        f"Parsed {n_points} timing points across {len(grouped)} variables from {args.log}"
    )
    print(f"Saved plot to {args.out}")


if __name__ == "__main__":
    main()
