"""Train scenario-specific double trees and test frozen winners on unseen streams."""
import argparse
import csv
import gc
import json
import multiprocessing
import random
from pathlib import Path
from statistics import fmean

from fogsim.training.config import TREES, EVOLUTION
from fogsim.training.deap_adapter import to_expression
from fogsim.training.dual_operators import initialize_dual, crossover_dual, mutate_dual, reproduce_dual
from fogsim.training.operators import choose_operator

from paper import SCALES, generate, simulate_sample


def expressions(trees):
    return tuple(to_expression(tree) for tree in trees)


def score(sample, pair):
    metrics = simulate_sample(sample, "MTGP", pair)
    gc.collect()
    return metrics["makespan"]


def run_trial(job):
    root, scale, devices, trial, pop_size, generations, elites, tournament_size, out = job
    # Heights count edges (ECJ depth counts nodes).
    limits = dict(TREES, init_min_height=1, init_max_height=5, max_height=7)
    rng = random.Random(50001 + trial)
    population = [initialize_dual(limits, rng)[0] for _ in range(pop_size)]
    history, candidates = [], []
    for gen in range(generations):
        seed = 1000000 + trial * 100000 + gen
        sample = generate(root, scale, devices, seed)
        fitness = {}
        pairs = [expressions(t) for t in population]
        for pair in pairs:
            if pair not in fitness:
                fitness[pair] = score(sample, pair)
        ordered = sorted(range(pop_size), key=lambda i: fitness[pairs[i]])
        best = pairs[ordered[0]]
        history.append(dict(generation=gen, instance_seed=seed, best=best,
                            makespan=fitness[best], unique=len(fitness)))
        if best not in candidates:
            candidates.append(best)
        del sample
        if gen + 1 == generations:
            break

        def parent():
            indices = [rng.randrange(pop_size) for _ in range(tournament_size)]
            return population[min(indices, key=lambda i: fitness[pairs[i]])]

        children = [population[i] for i in ordered[:elites]]
        while len(children) < pop_size:
            op, _ = choose_operator(EVOLUTION["operator_weights"], rng)
            if op == "crossover":
                result, _ = crossover_dual(parent(), parent(), limits,
                                           outputs=min(2, pop_size - len(children)), rng=rng)
            elif op == "mutation":
                result, _ = mutate_dual(parent(), limits, rng=rng)
            else:
                result, _ = reproduce_dual(parent())
            children.extend(result)
        population = children

    validation = {pair: [] for pair in candidates}
    for seed in range(80000, 80003):
        sample = generate(root, scale, devices, seed)
        for pair in candidates:
            validation[pair].append(score(sample, pair))
    selected = min(candidates, key=lambda p: fmean(validation[p]))
    prefix = out / f"{scale}-{devices}-trial-{trial + 1:02d}"
    record = dict(scale=scale, devices=devices, trial=trial + 1, evolution_seed=50001 + trial,
                  population=pop_size, generations=generations, elites=elites, history=history,
                  validation_seeds=list(range(80000, 80003)),
                  validation=[dict(pair=p, makespans=v) for p, v in validation.items()],
                  selected=dict(sequencing=selected[0], routing=selected[1]))
    prefix.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    with prefix.with_suffix(".csv").open("x", newline="") as f:
        writer = csv.DictWriter(f, fieldnames="scale devices trial seed method makespan workflows measured tasks events".split())
        writer.writeheader()
        for seed in range(90000, 90030):
            metrics = simulate_sample(generate(root, scale, devices, seed), "MTGP", selected)
            writer.writerow(dict(scale=scale, devices=devices, trial=trial+1, seed=seed, method="MTGP", **metrics))
            gc.collect()
    return prefix.name


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dax", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--profile", choices=("pilot", "long", "paper"), default="pilot")
    p.add_argument("--scales", choices=SCALES, nargs="+", default=list(SCALES))
    p.add_argument("--devices", type=int, choices=(1, 2, 3), nargs="+", default=(1, 2, 3))
    args = p.parse_args()
    profiles = {"pilot": (8, 3, 1, 3), "long": (32, 51, 2, 3), "paper": (1000, 51, 10, 30)}
    pop, gens, elites, trials = profiles[args.profile]
    args.out.mkdir(parents=True, exist_ok=False)
    # B04's smaller searches use its default of 3. The Java multi-tree
    # configuration supplies the tournament size omitted from Table VI.
    tournament_size = 7 if args.profile == "paper" else 3
    jobs = [(str(args.dax.resolve()), scale, devices, i, pop, gens, elites, tournament_size, args.out)
            for scale in args.scales for devices in args.devices for i in range(trials)]
    with multiprocessing.Pool(args.workers) as pool:
        for done in pool.imap_unordered(run_trial, jobs):
            print(done, flush=True)


if __name__ == "__main__":
    main()
