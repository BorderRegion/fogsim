"""Audit trial/instance pairing and compare held-out means at matched budgets."""
import argparse
import csv
import json
from math import isfinite
from pathlib import Path
from statistics import fmean, stdev


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_test(path, profile, ident, method):
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    test = {}
    for row in rows:
        key = row["scale"], int(row["devices"]), int(row["trial"])
        seed = int(row["seed"])
        makespan = float(row["makespan"])
        if key != ident or row["method"] != method or seed in test or not (isfinite(makespan) and makespan > 0):
            raise ValueError(f"Unpaired or duplicate {profile} test row in {path}")
        test[seed] = row
    if set(test) != set(range(90000, 90030)):
        raise ValueError(f"Incomplete test set in {path}")
    return test


def compare_trial(random_path, ref_path):
    ref, rs = read_json(ref_path), read_json(random_path)
    ident = ref["scale"], ref["devices"], ref["trial"]
    if (rs["scale"], rs["devices"], rs["trial"]) != ident or rs["search_seed"] != ref["evolution_seed"]:
        raise ValueError(f"Trial mismatch: {ident}")
    gp_plan = [(h["generation"], h["instance_seed"], h["unique"]) for h in ref["history"]]
    rs_plan = [(h["generation"], h["instance_seed"], h["evaluated"]) for h in rs["history"]]
    if gp_plan != rs_plan or rs["training_calls"] != sum(row[2] for row in gp_plan):
        raise ValueError(f"Training budgets differ: {ident}")
    if any(rs["history"][0][k] != ref["history"][0][k] for k in ("best", "makespan")):
        raise ValueError(f"First generation differs: {ident}")
    if rs["validation_seeds"] != ref["validation_seeds"] or len(rs["validation"]) != len(ref["validation"]):
        raise ValueError(f"Validation plans differ: {ident}")
    if {seed for _, seed, _ in gp_plan} & (set(rs["validation_seeds"]) | set(range(90000, 90030))):
        raise ValueError(f"Training seed overlaps with evaluation: {ident}")
    if set(rs["validation_seeds"]) & set(range(90000, 90030)):
        raise ValueError(f"Validation/test overlap: {ident}")
    for record in (rs, ref):
        vals = record["validation"]
        if len({tuple(v["pair"]) for v in vals}) != len(vals):
            raise ValueError(f"Duplicate validation candidate: {ident}")
        if any(len(v["makespans"]) != len(record["validation_seeds"]) for v in vals):
            raise ValueError(f"Missing validation scores: {ident}")
        if any(not (isfinite(x) and x > 0) for v in vals for x in v["makespans"]):
            raise ValueError(f"Invalid validation makespan: {ident}")
        if sum(len(v["makespans"]) for v in vals) != rs["validation_calls"]:
            raise ValueError(f"Validation cost mismatch: {ident}")
        winner = min(vals, key=lambda v: fmean(v["makespans"]))["pair"]
        if winner != [record["selected"][k] for k in ("sequencing", "routing")]:
            raise ValueError(f"Tested rule differs from validation winner: {ident}")
    profile = ref_path.parent.name
    mtgp = read_test(ref_path.with_suffix(".csv"), profile, ident, "MTGP")
    random = read_test(random_path.with_suffix(".csv"), profile, ident, "RandomSearch")
    for seed in mtgp:
        if any(mtgp[seed][k] != random[seed][k] for k in ("workflows", "measured", "tasks", "events")):
            raise ValueError(f"Instance mismatch: {ident}, seed {seed}")
    gp_mean = fmean(float(row["makespan"]) for row in mtgp.values())
    random_mean = fmean(float(row["makespan"]) for row in random.values())
    return dict(profile=profile, scale=ident[0], devices=ident[1], trial=ident[2],
                training_calls_each=rs["training_calls"], validation_calls_each=rs["validation_calls"],
                test_calls_each=len(mtgp), mtgp_mean=gp_mean, random_mean=random_mean,
                mtgp_minus_random=gp_mean-random_mean)


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def plot_pairs(path, rows, summary):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    fig, ax = plt.subplots(figsize=(8.3, 5.4), layout="constrained")
    colors = ("#26577c", "#b75a16", "#187662")
    labels = []
    for y, entry in enumerate(summary):
        key = entry["profile"], entry["scale"], entry["devices"]
        values = [r["mtgp_mean"]/r["random_mean"] for r in rows
                  if (r["profile"], r["scale"], r["devices"]) == key]
        ax.hlines(y, min(values), max(values), color="#aeb6bb", linewidth=1)
        for i, ratio in enumerate(values):
            ax.scatter(ratio, y + .12*(i-1), color=colors[i], s=32,
                       label=f"Seed {50001+i}" if y == 0 else None, zorder=3)
        label = f'{entry["scale"].title()} {entry["devices"]}'
        labels.append(label + (" (51 generations)" if key[0] == "long" else ""))
    ax.axvline(1, color="#333333", linestyle="--", linewidth=1)
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}×"))
    ax.set_yticks(range(len(labels)), labels)
    ax.invert_yaxis()
    ax.set_xlabel("MTGP / random search mean test makespan   (below 1 favors MTGP)")
    ax.set_title("Equal-budget search on the same 30 test instances per scenario", loc="left", pad=12)
    ax.legend(loc="best", fontsize=8)
    ax.grid(axis="x", alpha=.15)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference", type=Path, default=Path(__file__).resolve().parent/"results")
    p.add_argument("--random", type=Path, required=True)
    p.add_argument("--plot", action="store_true", help="also render a paired-trial comparison")
    args = p.parse_args()
    rows, summary = [], []
    for profile in ("pilot", "long"):
        groups = [(s, d) for s in ("small", "medium", "large") for d in (1, 2, 3)] if profile=="pilot" else [("small", 1)]
        for scale, devices in groups:
            group = []
            for trial in (1, 2, 3):
                rel = Path(profile)/f"{scale}-{devices}-trial-{trial:02d}.json"
                row = compare_trial(args.random/rel, args.reference/rel)
                group.append(row)
            rows.extend(group)
            gp = [r["mtgp_mean"] for r in group]
            rs = [r["random_mean"] for r in group]
            summary.append(dict(profile=profile, scale=scale, devices=devices,
                                mtgp_mean=fmean(gp), random_mean=fmean(rs),
                                mtgp_sd=stdev(gp), random_sd=stdev(rs),
                                mtgp_change_pct=100*(fmean(gp)/fmean(rs)-1),
                                mtgp_wins=sum(a<b for a,b in zip(gp,rs)),
                                ties=sum(a==b for a,b in zip(gp,rs)),
                                random_wins=sum(a>b for a,b in zip(gp,rs))))
    write_rows(args.random/"trials.csv", rows)
    write_rows(args.random/"summary.csv", summary)
    if args.plot:
        plot_pairs(args.random/"paired.png", rows, summary)
    for key in ("training_calls_each", "validation_calls_each", "test_calls_each"):
        print(key, sum(r[key] for r in rows))


if __name__ == "__main__":
    main()
