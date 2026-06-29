from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

LINE_RE = re.compile(
    r"^(?P<var>.+?)\s+CF:\s+(?P<cf>[0-9]*\.?[0-9]+)s,\s+"
    r"P5:\s+(?P<p5>[0-9]*\.?[0-9]+)s\s+\(WGD=(?P<wgd>Tru|Fal),\s*(?P<shape>.*)\)$"
)


@dataclass
class VarStats:
    name: str
    wgd: bool
    shape: tuple[int, ...] | None
    cf_times: list[float] = field(default_factory=list)
    p5_times: list[float] = field(default_factory=list)


def parse_shape(shape_text: str) -> tuple[int, ...] | None:
    shape_text = shape_text.strip()
    if not shape_text or shape_text == ")":
        return None

    try:
        parsed = ast.literal_eval(shape_text)
    except (SyntaxError, ValueError):
        return None

    if isinstance(parsed, tuple) and all(isinstance(x, int) for x in parsed):
        return parsed
    return None


def parse_log(log_path: Path) -> dict[str, VarStats]:
    records: dict[str, VarStats] = {}

    with log_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            match = LINE_RE.match(line)
            if match is None:
                continue

            var_name = match.group("var").strip()
            wgd = match.group("wgd") == "Tru"
            shape = parse_shape(match.group("shape"))
            cf_val = float(match.group("cf"))
            p5_val = float(match.group("p5"))

            if var_name not in records:
                records[var_name] = VarStats(
                    name=var_name, wgd=wgd, shape=shape
                )

            records[var_name].cf_times.append(cf_val)
            records[var_name].p5_times.append(p5_val)

    return records


def is_right_axis_shape(shape: tuple[int, ...] | None) -> bool:
    """Determine if a shape should use the right y-axis (239 or 240)."""
    return bool(
        shape is not None and len(shape) >= 1 and shape[0] in (239, 240)
    )


def shape_sort_key(var: VarStats) -> tuple:
    """Sort variables by shape group, then by name within group."""
    shape = var.shape

    # Determine group order
    if var.name == "meta":
        group = 0
    elif (
        shape is not None
        and len(shape) >= 2
        and shape[0] == 10
        and shape[1] == 1
    ):
        group = 1
    elif (
        shape is not None
        and len(shape) >= 2
        and shape[0] == 10
        and shape[1] == 2
    ):
        group = 2
    elif shape is not None and len(shape) >= 1 and shape[0] == 239:
        group = 3
    elif shape is not None and len(shape) >= 1 and shape[0] == 240:
        group = 4
    else:
        group = 5  # Other shapes

    return (group, var.name)


def make_combined_panel(ax, all_stats: list[VarStats]) -> None:
    """Create a single panel with dual y-axes, left for small shapes,
    right for 239/240."""
    if not all_stats:
        ax.set_title("No variables")
        ax.text(
            0.5,
            0.5,
            "No matching variables",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
        return

    # Sort by shape group, then by name
    all_stats = sorted(all_stats, key=shape_sort_key)
    n = len(all_stats)

    # Separate into left and right axis groups
    left_stats = [s for s in all_stats if not is_right_axis_shape(s.shape)]
    right_stats = [s for s in all_stats if is_right_axis_shape(s.shape)]

    # Create combined position array
    left_positions = list(range(len(left_stats)))
    right_positions = list(range(len(left_stats), n))

    # Prepare data
    left_cf = [s.cf_times for s in left_stats]
    left_p5 = [s.p5_times for s in left_stats]
    right_cf = [s.cf_times for s in right_stats]
    right_p5 = [s.p5_times for s in right_stats]

    # Plot left axis data
    cf_box_left = ax.boxplot(
        left_cf,
        positions=[p - 0.18 for p in left_positions],
        widths=0.32,
        patch_artist=True,
        manage_ticks=False,
    )
    p5_box_left = ax.boxplot(
        left_p5,
        positions=[p + 0.18 for p in left_positions],
        widths=0.32,
        patch_artist=True,
        manage_ticks=False,
    )

    # Create right axis and plot
    ax2 = ax.twinx()
    cf_box_right = ax2.boxplot(
        right_cf,
        positions=[p - 0.18 for p in right_positions],
        widths=0.32,
        patch_artist=True,
        manage_ticks=False,
    )
    p5_box_right = ax2.boxplot(
        right_p5,
        positions=[p + 0.18 for p in right_positions],
        widths=0.32,
        patch_artist=True,
        manage_ticks=False,
    )

    # Color all boxes
    for patch in cf_box_left["boxes"] + cf_box_right["boxes"]:
        patch.set_facecolor("#1f77b4")
        patch.set_alpha(0.7)
    for patch in p5_box_left["boxes"] + p5_box_right["boxes"]:
        patch.set_facecolor("#ff7f0e")
        patch.set_alpha(0.7)

    # Set x-axis with all labels, coloring WGD=True in red
    ax.set_xticks(range(n))
    labels = [s.name for s in all_stats]
    ax.set_xticklabels(labels, rotation=45, ha="right")

    # Color WGD=True labels red
    for i, s in enumerate(all_stats):
        if s.wgd:
            ax.get_xticklabels()[i].set_color("red")

    # Add vertical dotted line separating left and right axis groups
    if len(left_stats) > 0 and len(right_stats) > 0:
        divider_pos = len(left_stats) - 0.5
        y_min, y_max = ax.get_ylim()
        ax.vlines(
            divider_pos,
            y_min,
            y_max,
            colors="gray",
            linestyles="dotted",
            alpha=0.5,
            linewidth=1.5,
        )

    ax.set_ylabel("Seconds (left axis)", color="black")
    ax2.set_ylabel("Seconds (right axis, shapes 239/240)", color="black")
    ax.set_title(
        "CF vs P5 Variable Read Timings (shape-grouped with dual axes)"
    )
    ax.grid(axis="y", alpha=0.25)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot CF vs P5 timing distributions from comparison log"
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("doc/benchmarking/ppview-comparison-usb4.log"),
        help="Input benchmark log path",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("doc/benchmarking/ppview-comparison-usb4-boxplots.png"),
        help="Output image path",
    )
    args = parser.parse_args()

    records = parse_log(args.log)
    all_stats = list(records.values())

    fig, ax = plt.subplots(1, 1, figsize=(20, 6), constrained_layout=True)

    make_combined_panel(ax, all_stats)

    legend_handles = [
        Patch(facecolor="#1f77b4", alpha=0.7, label="CF"),
        Patch(facecolor="#ff7f0e", alpha=0.7, label="P5"),
    ]
    fig.legend(handles=legend_handles, loc="lower right")
    fig.suptitle(
        "CF vs P5 Variable Read Timings (8 repetitions) - Red labels = WGD=True",
        fontsize=14,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=180)
    plt.close(fig)

    print(f"Parsed {len(records)} variables from {args.log}")
    print(f"Saved plot to {args.out}")


if __name__ == "__main__":
    main()
