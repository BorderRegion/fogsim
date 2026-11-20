"""Cross-check experiment policy scores via their end-to-end task schedules.

Run with B04 src and tools on PYTHONPATH, a JDK 17 in FOGSIM_JAVA, and an
empty output folder. Recompile only the fixed data/observation adapter to
supply physical inputs and dispatch to the original Java algorithm classes.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess

from fogsim import RunConfig
from java_support import ADAPTER, ORIGINAL, prepare_and_compile
from run_fixed_parity import run_java_request
from paper import SCALES, BASELINES, generate, run_kernel


def build_adapter(out):
    java, classpath, _ = prepare_and_compile(out / "b04-build")
    original = (ADAPTER / "src/fogsim/adapter/FixedInstanceMain.java").read_text(encoding="utf-8")
    dispatch = "switch (str(config.get(\"paper_method\"))) {\n" + "\n".join(
        f'case "{name}" -> new mengxu.algorithm.{name}(type);' for name in BASELINES
    ) + 'default -> throw new IllegalArgumentException("paper_method");}'
    changes = {
        "final FCFS fcfs;": "final AbstractRule fcfs;",
        "fcfs = new FCFS(type)": "fcfs = " + dispatch,
        "FixedDevice(mobileId++)": 'FixedDevice(mobileId++, time(r.get("rate"), true))',
        "FixedDevice(int id) { super(id, state, sequencing, routing); }":
            "final double physicalRate; FixedDevice(int id, double rate) { super(id, state, sequencing, routing); physicalRate=rate; }"
            " @Override public double getProcessingRate() { return physicalRate; }",
        "ServerType.valueOf(type), 1.0, 1.0, 1.0":
            'ServerType.valueOf(type), time(r.get("up"),true), time(r.get("down"),true), time(r.get("rate"),true)',
        "task.setJob(job);": 'task.setWorkload(time(t.get("workload"),true)); task.setJob(job);',
    }
    for old, new in changes.items():
        if original.count(old) != 1:
            raise RuntimeError(f"Unexpected B04 adapter source at {old}")
        original = original.replace(old, new)
    src = out / "FixedInstanceMain.java"
    src.write_text(original, encoding="utf-8")
    classes = out / "paper-classes"
    classes.mkdir()
    javac = java.with_name("javac" + java.suffix)
    subprocess.run([str(javac), "-encoding", "UTF-8", "-d", str(classes), "-cp", classpath,
                    "-sourcepath", str(ORIGINAL / "src"), str(src)], check=True)
    return java, str(classes) + os.pathsep + classpath


def facts(result):
    return {k: result[k] for k in ("status", "makespan", "processed_event_count", "completed_workflow_count",
                                    "workflow_records", "task_records")}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dax", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--scale", choices=("check", *SCALES), default="check")
    p.add_argument("--devices", type=int, choices=(1, 2, 3), default=2)
    p.add_argument("--seed", type=int, default=4481)
    p.add_argument("--results-csv", type=Path, help="also verify the published warm-up window")
    args = p.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    java, cp = build_adapter(out)
    published = None
    if args.results_csv:
        with args.results_csv.open(encoding="utf-8", newline="") as f:
            published = {r["method"]: float(r["makespan"]) for r in csv.DictReader(f)
                         if (r["scale"], int(r["devices"]), int(r["seed"])) ==
                         (args.scale, args.devices, args.seed)}
    # Four full-size Class A DAX workloads contend for two shared servers.
    SCALES["check"] = (1, 3, 1, 5)
    sample = generate(args.dax, args.scale, args.devices, args.seed)
    inputs = sample.spec.to_dict()
    for r in inputs["resources"]:
        r["rate"] = sample.rates[r["id"]]
        if r["id"] in sample.links:
            r["up"], r["down"] = sample.links[r["id"]]
    for w in inputs["workflows"]:
        for t in w["tasks"]:
            t["workload"] = sample.workloads[w["id"], t["id"]]
    checks = []
    for name in BASELINES:
        cfg = RunConfig(trace_enabled=False, check_invariants=False)
        req = dict(schema_version=1, record_trace=False, input=inputs, config=dict(cfg.to_dict(), paper_method=name))
        ref = run_java_request(java, cp, req, out / name)["result"]
        got = facts(run_kernel(sample, name).__dict__)
        expected = facts(ref)
        # Java workflow records may additionally carry observation-only fields.
        for key in ("workflow_records", "task_records"):
            expected[key] = [{k: row[k] for k in got[key][0]} for row in expected[key]]
        (out / name / "python.json").write_text(json.dumps(got), encoding="utf-8")
        checks.append(dict(method=name, passed=got == expected, tasks=len(got["task_records"]),
                           events=got["processed_event_count"], python_makespan=got["makespan"],
                           java_makespan=expected["makespan"]))
        if published is not None:
            measured = [w for w in expected["workflow_records"] if w["workflow_id"] >= sample.warmup]
            window = max(w["completion_time"] for w in measured) - min(w["release_time"] for w in measured)
            checks[-1].update(scale=args.scale, devices=args.devices, seed=args.seed,
                              java_measured_makespan=window, python_csv_makespan=published[name])
            checks[-1]["passed"] &= window == published[name]
    (out / "summary.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2))
    return 0 if all(c["passed"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
