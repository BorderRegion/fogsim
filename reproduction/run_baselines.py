"""Run Table VII baselines on shared test instances in all Table V scenarios."""
import argparse
import csv
import multiprocessing
from pathlib import Path

from paper import BASELINES, SCALES, benchmark


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dax", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--instances", type=int, default=30)
    p.add_argument("--methods", nargs="+", choices=BASELINES, default=BASELINES)
    args = p.parse_args()
    if args.instances < 1 or args.workers < 1:
        p.error("instances and workers must be positive")
    jobs = [(str(args.dax.resolve()), scale, devices, 90000 + i, args.methods, None)
            for scale in SCALES for devices in (1, 2, 3) for i in range(args.instances)]
    with multiprocessing.Pool(args.workers) as pool, args.out.open("x", newline="") as f:
        table = csv.DictWriter(f, fieldnames="scale devices seed method makespan workflows measured tasks events".split())
        table.writeheader()
        for rows in pool.imap(benchmark, jobs):
            table.writerows(rows)
            f.flush()


if __name__ == "__main__":
    main()
