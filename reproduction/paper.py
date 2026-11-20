"""Finite Poisson workflow streams for Xu et al., Tables III–V.

Run with the extracted B04 src directory on PYTHONPATH. Each worker uses
one fresh event engine per rule. All methods see the same exogenous arrivals.
"""
import gc
import heapq
import random
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path
from unittest.mock import patch

from fogsim import RunConfig, parse_dax
from fogsim.instances.catalog import STANDARD_DAX_FILES
from fogsim.instances.spec import InstanceSpec, WorkflowSpec, ResourceSpec, TaskSpec, OptionSpec
from fogsim.rules.selection import is_preferred
from fogsim.simulation.engine import Engine
from fogsim.simulation.events import JobArrivalEvent
from fogsim.simulation.state import build_state
from fogsim.gp.parser import parse_expression
from fogsim.gp.program import compile_expression, Opcode
from fogsim.gp.ast import ConstantNode

SCALES = {"small": (10, 20, 20, 5), "medium": (15, 30, 30, 10), "large": (25, 50, 60, 15)}
BASELINES = ("FCFS", "MaxMin", "MinMin", "HEFT", "SDLS", "BWAWA", "CEAS")


def bandwidth(u):
    return 128 if u < .2 else 256 if u < .8 else 512


@lru_cache(maxsize=16)
def template(root, index):
    return parse_dax(Path(root) / STANDARD_DAX_FILES[index], dag_type_id=index)


@dataclass
class Sample:
    spec: InstanceSpec
    warmup: int
    tasks: int
    rates: dict
    links: dict
    workloads: dict


def generate(root, scale, devices, seed):
    warmup, recorded, servers, types = SCALES[scale]
    rng = random.Random(seed)
    mobiles = [ResourceSpec(f"M{i}", "MOBILE") for i in range(devices)]
    resources = list(mobiles)
    rates = {m.id: rng.uniform(125, 250) for m in mobiles}
    links = {}
    for kind, lower, upper in [("EDGE", 250, 500), ("CLOUD", 500, 1000)]:
        for i in range(servers):
            rid = f"{kind[0]}{i}"
            resources.append(ResourceSpec(rid, kind))
            rates[rid] = rng.uniform(lower, upper)
            links[rid] = (1024, 1024) if kind == "EDGE" else (bandwidth(rng.random()), bandwidth(rng.random()))
    arrivals = [(rng.expovariate(.01), m.id) for m in mobiles]
    heapq.heapify(arrivals)
    workflows, workloads = [], {}
    for wid in range(warmup + recorded):
        release, owner = heapq.heappop(arrivals)
        heapq.heappush(arrivals, (release + rng.expovariate(.01), owner))
        dag = template(root, rng.randrange(types))
        tasks = []
        for task in dag.tasks:
            work = rng.uniform(5000, 15000)
            workloads[wid, task.xml_id] = work
            upload, download = rng.randint(5220, 20680), rng.randint(5220, 20680)
            options = [OptionSpec(owner, 0., work / rates[owner], 0.)]
            options.extend(OptionSpec(rid, upload / up, work / rates[rid], download / down)
                           for rid, (up, down) in links.items())
            tasks.append(TaskSpec(task.xml_id, tuple(options)))
        workflows.append(WorkflowSpec(wid, owner, release, tuple(tasks), dag.dependencies))
    return Sample(InstanceSpec(tuple(resources), tuple(workflows)), warmup,
                  len(workloads), rates, links, workloads)


def score_function(expression):
    # Compile only instructions returned by the strict B04 parser. Template
    # fragments are fixed below. No user text is evaluated as Python.
    program = compile_expression(parse_expression(expression))
    features = dict(PT="o.processing_time", UT="o.upload_time", DT="o.download_time",
                    NIQ="float(len(o.resource.waiting_queue))", WIQ="o.resource.waiting_processing_time",
                    TTIQ="o.resource.waiting_total_time", MRT="o.resource.available_time",
                    TIS="(c.view.clock_time-o.task.workflow.release_time)",
                    TWT="(c.view.clock_time-o.ready_time)",
                    NTR="float(o.task.workflow.task_count-o.task.workflow.completed_task_count)")
    stack = []
    for instruction in program.instructions:
        if instruction.opcode == Opcode.PUSH_CONST:
            stack.append(repr(ConstantNode(instruction.operand).value))
        elif instruction.opcode == Opcode.READ_FEATURE:
            stack.append(features[instruction.operand.value])
        else:
            b, a = stack.pop(), stack.pop()
            fn = instruction.operand.value
            if fn in ("+", "-", "*"):
                stack.append(f"({a}{fn}{b})")
            else:
                name = {"/": "div", "Max": "maximum", "Min": "minimum"}[fn]
                stack.append(f"{name}({a},{b})")
    namespace = {"__builtins__": {}, "len": len, "float": float, "inf": float("inf"),
                 "div": lambda a, b: 1.0 if b == 0.0 else a / b,
                 "maximum": lambda a, b: a if b < a else b,
                 "minimum": lambda a, b: a if b > a else b}
    return eval("lambda o,c: " + stack[0], namespace)


def rules(method, sample, pair=None):
    if method == "MTGP":
        sequencing, routing = pair
        return score_function(routing), score_function(sequencing)
    sequence = {
        "FCFS": lambda o, c: o.task.workflow.release_time,
        "MinMin": lambda o, c: o.processing_time,
        "MaxMin": lambda o, c: -o.processing_time,
    }
    if method in sequence:
        return (lambda o, c: o.resource.available_time), sequence[method]

    # Task and TaskOption methods in the supplied Java implementation. Their
    # ranks depend only on this task's DAG, durations, rates and release time.
    @cache
    def durations(t):
        n = len(t.options)
        pt = sum(o.processing_time for o in t.options) / n
        up = sum(o.upload_time for o in t.options) / n
        down = sum(o.download_time for o in t.options) / n
        mean_rate = sum(sample.rates[o.resource.id] for o in t.options) / n
        return pt, up, down, sample.workloads[t.key] / mean_rate

    @cache
    def rank(t):
        pt, up, down, stochastic_pt = durations(t)
        if method == "BWAWA":
            if not t.parents:
                return t.workflow.release_time
            comm = max(durations(p)[2] + up for p in t.parents)
            return pt + comm + max(rank(p) for p in t.parents) + (0 if t.children else down)
        cost = stochastic_pt if method == "SDLS" else pt
        if not t.children:
            return cost + down - t.workflow.release_time
        tail = max(0., max((down + durations(ch)[1]) + rank(ch) for ch in t.children))
        return cost + tail + (0 if t.parents else up)

    def start(o):
        return max(o.ready_time, o.resource.available_time)

    if method == "HEFT":
        return (lambda o, c: start(o) + o.processing_time), (lambda o, c: -rank(o.task))
    if method == "SDLS":
        return (lambda o, c: -(rank(o.task) - start(o) + (durations(o.task)[3] - o.processing_time))), (lambda o, c: -rank(o.task))
    if method == "BWAWA":
        def band_rate(o, c):
            link = sample.links.get(o.resource.id)
            return 0.0 if link is None else 2.0 / sum(link)
        return band_rate, (lambda o, c: rank(o.task))
    if method == "CEAS":
        @cache
        def fastest(t):
            return min(o.processing_time for o in t.options)

        def utility(o, c):
            time = fastest(o.task) + o.download_time + o.upload_time
            return -(sample.workloads[o.task.key] / time - o.task.workflow.release_time)
        return utility, utility
    raise ValueError(method)


def select(context, score, recorder):
    # Only closed, read-only experiment scores enter here. B04's total ordering
    # includes signed zero, NaN and workflow tie-breaks.
    best = None
    for option in context.candidates:
        option.priority = score(option, context)
        if best is None or is_preferred(option, best):
            best = option
    return best


def run_kernel(sample, method, pair=None):
    from fogsim.simulation import engine as event_module
    state = build_state(sample.spec)
    engine = Engine(state, RunConfig(trace_enabled=False, check_invariants=False))
    engine.routing_rule, engine.sequencing_rule = rules(method, sample, pair)
    for workflow in state.workflows_by_id.values():
        engine.event_queue.stage(JobArrivalEvent(workflow), workflow.owner_device)
    # Processes run sequential simulations. Override only the two decision calls
    # within this context, leaving the simulator's event and queue code intact.
    with patch.object(event_module, "choose_route", select), patch.object(event_module, "choose_next", select):
        result = engine.run()
    if result.status != "SUCCEEDED" or result.completed_workflow_count != len(sample.spec.workflows):
        raise RuntimeError((result.status, result.reason, result.completed_workflow_count))
    return result


def simulate_sample(sample, method, pair=None):
    result = run_kernel(sample, method, pair)
    records = [w for w in result.workflow_records if w["workflow_id"] >= sample.warmup]
    return dict(makespan=max(w["completion_time"] for w in records) - min(w["release_time"] for w in records),
                workflows=result.completed_workflow_count, measured=len(records), tasks=sample.tasks,
                events=result.processed_event_count)


def benchmark(job):
    root, scale, devices, seed, methods, pair = job
    sample = generate(root, scale, devices, seed)
    rows = []
    for method in methods:
        metrics = simulate_sample(sample, method, pair)
        rows.append(dict(scale=scale, devices=devices, seed=seed, method=method, **metrics))
        gc.collect()
    return rows
