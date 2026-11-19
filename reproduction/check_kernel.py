"""Compare paper-runner schedules and expression scores with B04's checked path."""
import argparse
import json
import struct
from pathlib import Path

from fogsim import load_fixed_instance, RunConfig, simulate
from fogsim.gp.evaluator import evaluate
from fogsim.gp.parser import parse_expression
from fogsim.gp.program import compile_expression
from fogsim.rules.contexts import RoutingContext, StateView
from fogsim.simulation.state import build_state
from paper import Sample, bandwidth, run_kernel, score_function

PAIRS = [
    ("PT", "MRT"),
    ("(- 0 PT)", "(+ (+ UT DT) (+ PT TTIQ))"),
    ("(/ TIS TWT)", "(Max (Min NIQ NTR) (* WIQ MRT))"),
    ("(/ PT -0.0)", "(Min -0.0 0.0)"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    boundary_values = [bandwidth(x) for x in (0., .19999999, .2, .79999999, .8, .99999999)]
    if boundary_values != [128, 128, 256, 256, 512, 512]:
        raise ValueError("Incorrect cloud bandwidth intervals")
    rows = []
    for case in ("v2_diamond", "v2_shared_server", "v2_contention", "v2_order"):
        spec = load_fixed_instance(args.cases / (case + ".json"))
        sample = Sample(spec, 0, sum(len(w.tasks) for w in spec.workflows), {}, {}, {})
        state = build_state(spec)
        for seq, route in PAIRS:
            evaluations = 0
            for expr in (seq, route):
                program = compile_expression(parse_expression(expr))
                compiled = score_function(expr)
                for task in state.tasks_by_key.values():
                    ctx = RoutingContext(task, tuple(task.options), StateView.from_state(state))
                    for option in ctx.candidates:
                        actual = compiled(option, ctx)
                        expected = evaluate(program, option, ctx)
                        if struct.pack(">d", actual) != struct.pack(">d", expected):
                            raise AssertionError((case, expr, actual, expected))
                        evaluations += 1
            standard = simulate(spec, RunConfig(routing_kind="gp", routing_expression=route,
                                sequencing_kind="gp", sequencing_expression=seq, trace_enabled=False))
            paper = run_kernel(sample, "MTGP", (seq, route))
            keys = ["status", "processed_event_count", "completed_workflow_count", "makespan",
                    "workflow_records", "task_records"]
            if standard.status != "SUCCEEDED" or any(getattr(standard, k) != getattr(paper, k) for k in keys):
                raise AssertionError((case, seq, route))
            rows.append(dict(case=case, sequencing=seq, routing=route, passed=True,
                             bitwise_score_checks=evaluations, events=paper.processed_event_count))
    args.out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} schedule comparisons passed")


if __name__ == "__main__":
    main()
