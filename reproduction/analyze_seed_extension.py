"""Verify all original trial artifacts, then bootstrap paired training seeds."""
import argparse
import csv
import json
from math import comb
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import numpy as np

from analyze_random_search import compare_trial

SEEDS = range(50004, 50034)
SCENARIOS = [(s, d) for s in ("small", "medium", "large") for d in (1, 2, 3)]


def collect(root):
    rows = []
    for profile in ("pilot", "long"):
        for scale, devices in SCENARIOS if profile == "pilot" else [("small", 1)]:
            for seed in SEEDS:
                label = f"{scale}-{devices}-trial-{seed-50000:02d}"
                case = root/profile/label
                raw = json.loads((case/"paired.json").read_text())
                gp_path = case/"mtgp"/profile/(label+".json")
                rs_path = case/"random"/profile/(label+".json")
                verified = compare_trial(rs_path, gp_path)
                gp = json.loads(gp_path.read_text())
                if gp["evolution_seed"] != seed or raw["seed"] != seed:
                    raise ValueError(f"Wrong seed: {case}")
                if any(value != raw[key] for key, value in verified.items()):
                    raise ValueError(f"Cluster result differs from recomputed result: {case}")
                rows.append(dict(seed=seed, **verified))
    if len(list(root.glob("*/*/paired.json"))) != len(rows):
        raise ValueError("Unexpected trial count")
    return rows


def sign_p(wins, losses):
    n = wins + losses
    return min(1., 2*sum(comb(n, i) for i in range(min(wins, losses)+1))/2**n)


def summarize(profile, scenario, gp, rs, draws):
    # Rows are independent training seeds. Columns are paired scenarios.
    ratios = gp/rs
    log_r = np.log(ratios).mean(axis=1)
    change = lambda x: 100*np.expm1(x)
    low, high = change(np.quantile(log_r[draws].mean(axis=1), [.025, .975]))
    w, l = int((log_r < 0).sum()), int((log_r > 0).sum())
    return dict(profile=profile, scenario=scenario, seeds=len(log_r),
                mtgp_arithmetic_mean_s=gp.mean(), random_arithmetic_mean_s=rs.mean(),
                mtgp_change_pct=change(log_r.mean()), ci95_low_pct=low, ci95_high_pct=high,
                median_paired_ratio=np.median(np.exp(log_r)), mtgp_wins=w,
                ties=len(log_r)-w-l, random_wins=l,
                sign_p=sign_p(w,l) if profile=="long" or scenario=="nine_equal_weight" else "",
                holm_p="")


def write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def plot_primary(path, panels):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator, FuncFormatter

    fig, axes = plt.subplots(2, 1, figsize=(9, 5.8), sharex=True, layout="constrained")
    for ax, (title, ratios, result) in zip(axes, panels):
        low, high = [1 + result[k]/100 for k in ("ci95_low_pct", "ci95_high_pct")]
        center = 1 + result["mtgp_change_pct"]/100
        ax.set_yscale("log", base=2)
        ax.axhspan(low, high, color="#c5deea", alpha=.7)
        ax.axhline(center, color="#276383", linewidth=1.5)
        ax.axhline(1, color="#333333", linestyle="--", linewidth=1)
        ax.scatter(list(SEEDS), ratios, s=22, color="#20333f", zorder=3)
        ax.yaxis.set_major_locator(FixedLocator([.5,.75,1,1.25,1.5,2,3]))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_: f"{x:g}×"))
        ax.set_ylim(min(min(ratios),low)*.93,max(max(ratios),high)*1.08)
        ax.set_title(title, loc="left", fontsize=12)
        ax.set_ylabel("MTGP / random")
    axes[-1].set_xlabel("Training seed\nBlue line and band show the geometric mean and its 95% bootstrap interval.")
    fig.suptitle("Paired test makespan by training seed", fontsize=16)
    fig.savefig(path,dpi=150)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("evidence", type=Path, help="ZIP or extracted directory containing runs/")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--plot", action="store_true")
    args = p.parse_args()
    with TemporaryDirectory() as tmp:
        root = args.evidence
        if not root.is_dir():
            with ZipFile(root) as z:
                z.extractall(tmp)
            root = Path(tmp)
        rows = collect(root/"runs")
    table = {(r["profile"],r["scale"],r["devices"],r["seed"]):r for r in rows}
    draws = np.random.default_rng(20261119).integers(len(SEEDS), size=(50000, len(SEEDS)))
    stats, panels = [], []
    for profile, cols in [("pilot", SCENARIOS), ("long", [("small",1)])]:
        mats = [np.array([[table[profile,s,d,i][key] for s,d in cols] for i in SEEDS])
                for key in ("mtgp_mean", "random_mean")]
        if profile == "pilot":
            stats.append(summarize(profile, "nine_equal_weight", *mats, draws))
        for col,(s,d) in enumerate(cols):
            stats.append(summarize(profile, f"{s}_{d}", mats[0][:,[col]], mats[1][:,[col]], draws))
        label = "3 generations · nine scenarios, equal weights" if profile == "pilot" else "51 generations · Small 1"
        panels.append((label, np.exp(np.log(mats[0]/mats[1]).mean(axis=1)), stats[0] if profile=="pilot" else stats[-1]))
    first, second = sorted([stats[0],stats[-1]], key=lambda r:r["sign_p"])
    first["holm_p"] = min(1., 2*first["sign_p"])
    second["holm_p"] = max(first["holm_p"], second["sign_p"])
    args.out.mkdir(parents=True, exist_ok=True)
    write(args.out/"paired-trials.csv", rows)
    write(args.out/"summary.csv", stats)
    if args.plot:
        plot_primary(args.out/"seed-comparison.png", panels)


if __name__ == "__main__":
    main()
