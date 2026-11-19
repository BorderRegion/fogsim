"""Plot percentage differences from the published Table VII means."""
import csv
from pathlib import Path
import argparse

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True)
    args = p.parse_args()
    with (args.results / "summary.csv").open(encoding="utf-8") as f:
        values = {(r["scale"], int(r["devices"]), r["method"]): float(r["difference_pct"])
                  for r in csv.DictReader(f) if r["profile"] != "long"}
    scales = ("small", "medium", "large")
    methods = ("HEFT", "FCFS", "MaxMin", "MinMin", "SDLS", "BWAWA", "CEAS", "MTGP")
    scenarios = [(s, d) for s in scales for d in (1, 2, 3)]
    matrix = np.array([[values[s, d, method] for method in methods] for s, d in scenarios])
    fig, ax = plt.subplots(figsize=(9.2, 5.5), layout="constrained")
    norm = TwoSlopeNorm(0, vmin=-max(20, abs(matrix.min())), vmax=max(20, matrix.max()))
    colors = plt.get_cmap("RdBu_r")
    ax.imshow(matrix, cmap=colors, norm=norm, aspect="auto")
    for (row, col), val in np.ndenumerate(matrix):
        r, g, b, _ = colors(norm(val))
        color = "white" if .213*r + .715*g + .072*b < .48 else "#181c21"
        ax.text(col, row, f"{val:+.1f}%", ha="center", va="center", fontsize=9, color=color)
    for y in (2.5, 5.5):
        ax.axhline(y, color="white", linewidth=2)
    ax.set_xticks(range(len(methods)), [*methods[:-1], "MTGP pilot"])
    ax.set_yticks(range(len(scenarios)), [f"{s.capitalize()} {d}" for s, d in scenarios])
    ax.xaxis.tick_top()
    ax.tick_params(length=0, pad=7)
    ax.set_title("Mean makespan relative to Table VII", loc="left", pad=16, weight="bold", fontsize=16)
    ax.set_xlabel("Positive values indicate a longer makespan than published. All methods share 30 test instances per scenario.",
                  fontsize=9, labelpad=12)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.savefig(args.results / "table-vii.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
