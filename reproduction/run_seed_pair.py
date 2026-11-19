"""Run one fresh paired seed using the frozen MTGP and random-search protocols."""
import argparse
import csv
import json
import os
import platform
from pathlib import Path
from time import monotonic
from importlib.metadata import version

from analyze_random_search import compare_trial
from run_mtgp import run_trial as evolve
from run_random_search import run_trial as random_search

PROFILES = {"pilot": (8, 3, 1), "long": (32, 51, 2)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", required=True, choices=PROFILES)
    p.add_argument("--scale", required=True, choices=("small", "medium", "large"))
    p.add_argument("--devices", required=True, type=int, choices=(1, 2, 3))
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--dax", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    if args.seed < 50001 or (args.profile == "long" and (args.scale, args.devices) != ("small", 1)):
        p.error("Unsupported seed or long scenario")
    trial = args.seed - 50001
    label = f"{args.scale}-{args.devices}-trial-{trial+1:02d}"
    dest = args.out/args.profile/label
    done = dest/"paired.json"
    if done.exists():
        raise FileExistsError(done)
    mtgp = dest/"mtgp"/args.profile
    rs = dest/"random"
    mtgp.mkdir(parents=True, exist_ok=True)
    (rs/args.profile).mkdir(parents=True, exist_ok=True)
    reference = mtgp/(label+".json")
    # Freeze and persist both rule pairs before accessing their test scores.
    start = monotonic()
    evolve((args.dax, args.scale, args.devices, trial, *PROFILES[args.profile], 3, mtgp))
    gp_end = monotonic()
    random_search((args.dax, reference, rs))
    result = compare_trial(rs/args.profile/reference.name, reference)
    result.update(seed=args.seed, mtgp_seconds=gp_end-start, random_seconds=monotonic()-gp_end,
                  python=platform.python_version(), numpy=version("numpy"), deap=version("deap"),
                  job_id=os.environ.get("SLURM_JOB_ID"))
    tmp = done.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    tmp.replace(done)
    print(label, json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
