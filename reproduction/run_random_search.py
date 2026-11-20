"""Compare independent random dual trees with archived MTGP simulator budgets."""
import argparse
import csv
import gc
import json
import multiprocessing
import random
from pathlib import Path
from statistics import fmean

from fogsim.training.config import TREES
from fogsim.training.dual_operators import initialize_dual
from paper import generate, simulate_sample
from run_mtgp import expressions, score


def best_distinct(entries):
    # Stable order breaks exact ties by first observation.
    return list(dict.fromkeys(pair for value, pair in sorted(entries, key=lambda x: x[0])))


def run_trial(job):
    root, reference, destination = job
    ref = json.loads(reference.read_text(encoding="utf-8"))
    scale, devices, trial = ref["scale"], ref["devices"], ref["trial"]
    limits = dict(TREES, init_min_height=1, init_max_height=5, max_height=7)
    rng = random.Random(ref["evolution_seed"])
    history, winners, scored = [], [], []
    for gen in ref["history"]:
        sample = generate(root, scale, devices, gen["instance_seed"])
        fitness = {}
        while len(fitness) < gen["unique"]:
            pair = expressions(initialize_dual(limits, rng)[0])
            if pair not in fitness:
                fitness[pair] = score(sample, pair)
        winner = min(fitness, key=fitness.get)
        if gen["generation"] == 0 and (list(winner) != gen["best"] or fitness[winner] != gen["makespan"]):
            raise ValueError("Shared initial population check failed")
        winners.append((fitness[winner], winner))
        scored.extend((v, pair) for pair, v in fitness.items())
        history.append(dict(generation=gen["generation"], instance_seed=gen["instance_seed"],
                            evaluated=len(fitness), best=winner, makespan=fitness[winner]))
        del sample

    # MTGP validates distinct generation winners. Its realized budget may be
    # smaller than the number of batches. Keep the lowest training makespans
    # among random batch winners; fill any shortfall from other sampled trees.
    k = len(ref["validation"])
    shortlist = best_distinct(winners)
    if len(shortlist) < k:
        chosen = set(shortlist)
        shortlist.extend(pair for pair in best_distinct(scored) if pair not in chosen)
    shortlist = shortlist[:k]
    if len(shortlist) != k:
        raise RuntimeError("Insufficient distinct rules for the matched validation budget")
    validation = {pair: [] for pair in shortlist}
    for seed in ref["validation_seeds"]:
        sample = generate(root, scale, devices, seed)
        for pair in shortlist:
            validation[pair].append(score(sample, pair))
    selected = min(validation, key=lambda p: fmean(validation[p]))
    prefix = destination / reference.parent.name / reference.stem
    validation_runs = sum(map(len, validation.values()))
    record = dict(scale=scale, devices=devices, trial=trial, search_seed=ref["evolution_seed"],
                  mtgp_reference=reference.parent.name+"/"+reference.name, history=history,
                  validation_seeds=ref["validation_seeds"],
                  validation=[dict(pair=p, makespans=v) for p,v in validation.items()],
                  selected=dict(sequencing=selected[0], routing=selected[1]),
                  training_calls=sum(h["evaluated"] for h in history), validation_calls=validation_runs)
    prefix.with_suffix(".json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    with reference.with_suffix(".csv").open(encoding="utf-8", newline="") as f:
        test_plan = list(csv.DictReader(f))
    if [int(r["seed"]) for r in test_plan] != list(range(90000, 90030)):
        raise ValueError("Unexpected test seed plan")
    with prefix.with_suffix(".csv").open("x", newline="", encoding="utf-8") as f:
        fields = "scale devices trial seed method makespan workflows measured tasks events".split()
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in test_plan:
            seed = int(row["seed"])
            metrics = simulate_sample(generate(root, scale, devices, seed), "MTGP", selected)
            if any(metrics[k] != int(row[k]) for k in ("workflows", "measured", "tasks", "events")):
                raise ValueError("Mismatch with MTGP test instance")
            writer.writerow(dict(scale=scale, devices=devices, trial=trial, seed=seed, method="RandomSearch", **metrics))
            gc.collect()
    return f"{reference.parent.name}/{reference.stem}"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dax", required=True, type=Path)
    p.add_argument("--reference", type=Path, default=Path(__file__).resolve().parent/"results")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--workers", default=4, type=int)
    args = p.parse_args()
    if args.workers < 1:
        p.error("--workers must be positive")
    jobs = []
    for profile, expected in (("long", 3), ("pilot", 27)):
        refs = sorted((args.reference / profile).glob("*.json"))
        if len(refs) != expected:
            p.error(f"Expected {expected} MTGP trials for {profile}")
        jobs.extend((args.dax.resolve(), path, args.out.resolve()) for path in refs)
    args.out.mkdir(parents=True, exist_ok=False)
    for profile in ("long", "pilot"):
        (args.out / profile).mkdir()
    with multiprocessing.Pool(args.workers) as pool:
        for name in pool.imap_unordered(run_trial, jobs):
            print(name, flush=True)


if __name__ == "__main__":
    main()
