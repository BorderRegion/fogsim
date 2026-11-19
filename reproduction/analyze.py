"""Validate raw test membership and summarize Table VII comparisons."""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean, stdev

BASELINES = ("HEFT", "FCFS", "MaxMin", "MinMin", "SDLS", "BWAWA", "CEAS")
SIZES = {"small": (30, 20), "medium": (45, 30), "large": (75, 50)}
SEEDS = set(range(90000, 90030))


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def summarize(results):
    here = Path(__file__).resolve().parent
    paper = {(r["scale"], int(r["devices"])): r for r in read_csv(here / "paper_table_vii.csv")}
    groups, checks = defaultdict(dict), {}
    def add(row, profile, trial):
        scale, devices, seed, method = row["scale"], int(row["devices"]), int(row["seed"]), row["method"]
        key = (scale, devices, method, profile, trial)
        val = float(row["makespan"])
        if seed in groups[key] or not math.isfinite(val) or val <= 0:
            raise ValueError((key, seed, val))
        facts = tuple(int(row[k]) for k in ("workflows", "measured", "tasks", "events"))
        if facts[:2] != SIZES[scale] or facts[3] != 3 * facts[2] + facts[0]:
            raise ValueError((key, seed, facts))
        if facts != checks.setdefault((scale, devices, seed), facts):
            raise ValueError(f"Inconsistent scenario input: {key} seed {seed}")
        groups[key][seed] = val

    for row in read_csv(results / "baselines.csv"):
        add(row, "baseline", 0)
    for profile in ("pilot", "long"):
        for path in (results / profile).glob("*.csv"):
            rule = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            if set(rule["validation_seeds"]) & SEEDS or any(h["instance_seed"] in SEEDS for h in rule["history"]):
                raise ValueError("Test seed reused in training or validation")
            winner = min(rule["validation"], key=lambda r: fmean(r["makespans"]))
            if winner["pair"] != [rule["selected"][k] for k in ("sequencing", "routing")]:
                raise ValueError("Rule differs from validation winner")
            for row in read_csv(path):
                if (row["scale"], int(row["devices"]), int(row["trial"]), row["method"]) != (
                        rule["scale"], rule["devices"], rule["trial"], "MTGP"):
                    raise ValueError(f"Rule/test mismatch: {path}")
                add(row, profile, rule["trial"])

    expected = {(s, d, m, "baseline", 0) for s in SIZES for d in (1, 2, 3) for m in BASELINES}
    expected.update((s, d, "MTGP", "pilot", t) for s in SIZES for d in (1, 2, 3) for t in (1, 2, 3))
    expected.update(("small", 1, "MTGP", "long", t) for t in (1, 2, 3))
    if groups.keys() != expected or any(set(values) != SEEDS for values in groups.values()):
        raise ValueError("Missing or extra scenario, method, trial or test seed")
    rows = []
    for scale in SIZES:
        for devices in (1, 2, 3):
            for method, profile in [*((m, "baseline") for m in BASELINES), ("MTGP", "pilot"), ("MTGP", "long")]:
                runs = [list(v.values()) for k, v in groups.items() if k[:4] == (scale, devices, method, profile)]
                if not runs:
                    continue
                means = [fmean(r) for r in runs]
                observed = fmean(means)
                ref = float(paper[scale, devices][method])
                rows.append(dict(scale=scale, devices=devices, method=method, profile=profile, rules=len(runs),
                                 test_instances=len(SEEDS), mean=observed, paper_mean=ref,
                                 difference_pct=100*(observed/ref-1), sd_between_trials=stdev(means) if len(means)>1 else "",
                                 mean_within_rule_test_sd=fmean(stdev(r) for r in runs)))
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True, type=Path)
    args = p.parse_args()
    rows = summarize(args.results)
    with (args.results / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} scenario/method/profile comparisons")
