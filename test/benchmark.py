#!/usr/bin/env python3
"""Collect quantitative metrics from optimize4 algorithm tests.

Runs test/sqp, test/pgd, test/penalty, and test/unconstrained scripts with
morpho6, parses iteration output, and groups results by example problem.

Usage:
  python3 test/benchmark.py              # all algorithm tests
  python3 test/benchmark.py loop nematic # subset by example name
  python3 test/benchmark.py --json       # machine-readable output
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_ROOT = os.path.join(ROOT, "test")
TEST_BIN = os.path.join(TEST_ROOT, "bin")
COMMAND = "morpho6"

ALGO_DIRS = ("sqp", "pgd", "penalty", "unconstrained")

ITER_RE = re.compile(
    r"Iteration\s+(\d+):\s+([\d.eE+-]+)\s+\|grad\|=([\d.eE+-]+)"
    r"(?:\s+\|constraints\|=([\d.eE+-]+))?"
    r"(?:\s+stepsize=([\d.eE+-]+))?"
)
PENALTY_RE = re.compile(
    r"==Penalty iteration\s+(\d+):\s+mu=([\d.eE+-]+)\s+\|constraints\|=([\d.eE+-]+)"
)
EXAMPLE_IMPORT_RE = re.compile(r'import\s+"\.\./examples/([^"]+\.morpho)"')
CI_IGNORE_RE = re.compile(r"\[CI:\s*Ignore\s*\]", re.I)
CI_SMOKE_RE = re.compile(r"\[CI:\s*Smoke\s*\]", re.I)
WARN_MAXITER_RE = re.compile(r"Warning\s+'OptMaxIter'")
WARN_LNSRCH_RE = re.compile(r"Warning\s+'OptLnSrchStpsz'")


@dataclass
class RunMetrics:
    path: str
    algorithm: str
    example: str
    ignored: bool = False
    smoke: bool = False
    wall_s: float = 0.0
    converged: bool = False
    outer_iters: int = 0
    inner_iters: int = 0
    total_iters: int = 0
    final_obj: Optional[float] = None
    final_grad: Optional[float] = None
    final_cons: Optional[float] = None
    penalty_outer: int = 0
    maxiter_warn: bool = False
    lnsrch_warn: bool = False
    error: str = ""


def headless_env() -> dict:
    env = os.environ.copy()
    env["PATH"] = TEST_BIN + os.pathsep + env.get("PATH", "")
    return env


def discover_tests(names: Optional[Sequence[str]] = None) -> List[str]:
    files: List[str] = []
    for algo in ALGO_DIRS:
        files.extend(glob.glob(os.path.join(TEST_ROOT, algo, "*.morpho")))
    files = sorted(files)
    if not names:
        return files
    wanted = {n.lower().replace(".morpho", "") for n in names}
    out = []
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0].lower()
        if base in wanted:
            out.append(f)
    return out


def parse_example(path: str) -> str:
    with open(path, encoding="utf8") as fh:
        text = fh.read()
    m = EXAMPLE_IMPORT_RE.search(text)
    if m:
        return os.path.splitext(os.path.basename(m.group(1)))[0]
    return os.path.splitext(os.path.basename(path))[0]


def parse_flags(path: str) -> Tuple[bool, bool]:
    with open(path, encoding="utf8") as fh:
        text = fh.read()
    return bool(CI_IGNORE_RE.search(text)), bool(CI_SMOKE_RE.search(text))


def check_converged_output(algo: str, raw: str) -> Tuple[bool, bool, bool]:
    """Return (converged, maxiter_terminal, lnsrch) using test.py rules."""
    maxiter = bool(WARN_MAXITER_RE.search(raw))
    lnsrch = bool(WARN_LNSRCH_RE.search(raw))

    if maxiter and algo == "penalty":
        lines = raw.splitlines()
        terminal = True
        for i, line in enumerate(lines):
            if not WARN_MAXITER_RE.search(line):
                continue
            rest = "\n".join(lines[i + 1 :])
            if "==Penalty iteration" in rest:
                terminal = False
                break
        maxiter = terminal

    converged = not maxiter and not lnsrch
    return converged, maxiter, lnsrch


def parse_output(algo: str, raw: str) -> Tuple[dict, bool, bool, bool]:
    iterations: List[Tuple[int, float, float, Optional[float]]] = []
    penalty_rows: List[Tuple[int, float, float]] = []

    for line in raw.splitlines():
        pm = PENALTY_RE.search(line)
        if pm:
            penalty_rows.append((int(pm.group(1)), float(pm.group(2)), float(pm.group(3))))
            continue
        im = ITER_RE.search(line)
        if im:
            cons = float(im.group(4)) if im.group(4) else None
            iterations.append((int(im.group(1)), float(im.group(2)), float(im.group(3)), cons))

    converged, maxiter, lnsrch = check_converged_output(algo, raw)

    metrics: dict = {
        "outer_iters": 0,
        "inner_iters": 0,
        "total_iters": 0,
        "final_obj": None,
        "final_grad": None,
        "final_cons": None,
        "penalty_outer": len(penalty_rows),
    }

    if algo == "penalty":
        metrics["outer_iters"] = len(penalty_rows)
        metrics["inner_iters"] = len(iterations)
        metrics["total_iters"] = metrics["inner_iters"]
        if penalty_rows:
            metrics["final_cons"] = penalty_rows[-1][2]
        if iterations:
            _, obj, grad, cons = iterations[-1]
            metrics["final_obj"] = obj
            metrics["final_grad"] = grad
            if cons is not None:
                metrics["final_cons"] = cons
    else:
        metrics["outer_iters"] = len(iterations)
        metrics["total_iters"] = len(iterations)
        if iterations:
            _, obj, grad, cons = iterations[-1]
            metrics["final_obj"] = obj
            metrics["final_grad"] = grad
            metrics["final_cons"] = cons

    return metrics, converged, maxiter, lnsrch


def run_test(path: str) -> RunMetrics:
    rel = os.path.relpath(path, TEST_ROOT)
    algo = rel.split(os.sep)[0]
    example = parse_example(path)
    ignored, smoke = parse_flags(path)

    proc = subprocess.run(
        [COMMAND, path],
        cwd=ROOT,
        env=headless_env(),
        capture_output=True,
        text=True,
    )
    raw = (proc.stdout or "") + (proc.stderr or "")

    metrics, converged, maxiter, lnsrch = parse_output(algo, raw)
    error = ""
    if proc.returncode != 0:
        error = f"exit {proc.returncode}"

    return RunMetrics(
        path=rel,
        algorithm=algo,
        example=example,
        ignored=ignored,
        smoke=smoke,
        converged=converged and proc.returncode == 0,
        outer_iters=metrics["outer_iters"],
        inner_iters=metrics["inner_iters"],
        total_iters=metrics["total_iters"],
        final_obj=metrics["final_obj"],
        final_grad=metrics["final_grad"],
        final_cons=metrics["final_cons"],
        penalty_outer=metrics["penalty_outer"],
        maxiter_warn=maxiter,
        lnsrch_warn=lnsrch,
        error=error,
    )


def run_timed(path: str) -> RunMetrics:
    import time

    t0 = time.perf_counter()
    result = run_test(path)
    result.wall_s = time.perf_counter() - t0
    return result


def group_by_example(results: Sequence[RunMetrics]) -> Dict[str, List[RunMetrics]]:
    groups: Dict[str, List[RunMetrics]] = {}
    for r in results:
        groups.setdefault(r.example, []).append(r)
    for g in groups.values():
        g.sort(key=lambda x: (ALGO_DIRS.index(x.algorithm) if x.algorithm in ALGO_DIRS else 99, x.algorithm))
    return dict(sorted(groups.items()))


def fmt_float(x: Optional[float], prec: int = 4) -> str:
    if x is None:
        return "-"
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 1e4 or (ax > 0 and ax < 1e-3):
        return f"{x:.3e}"
    return f"{x:.{prec}f}"


def print_table(results: Sequence[RunMetrics]) -> None:
    groups = group_by_example(results)
    print(f"{'Example':<22} {'Algo':<12} {'OK':<4} {'Time(s)':<8} {'Iters':<7} {'Outer':<6} {'|c|':<10} {'Objective':<12} {'|grad|':<10} Notes")
    print("-" * 110)
    for example, rows in groups.items():
        for r in rows:
            notes = []
            if r.ignored:
                notes.append("ignored")
            if r.smoke:
                notes.append("smoke")
            if r.maxiter_warn:
                notes.append("OptMaxIter")
            if r.lnsrch_warn:
                notes.append("OptLnSrchStpsz")
            if r.error:
                notes.append(r.error)
            if r.algorithm == "penalty":
                iter_s = str(r.inner_iters)
                outer_s = str(r.penalty_outer)
            else:
                iter_s = str(r.total_iters)
                outer_s = "-"
            ok = "yes" if r.converged else "no"
            print(
                f"{example:<22} {r.algorithm:<12} {ok:<4} {r.wall_s:>7.2f} {iter_s:<7} {outer_s:<6} "
                f"{fmt_float(r.final_cons):<10} {fmt_float(r.final_obj):<12} {fmt_float(r.final_grad):<10} "
                f"{' '.join(notes)}"
            )
        print()


def print_summary(results: Sequence[RunMetrics]) -> None:
    mesh_examples = {
        "loop", "nematic", "tactoid", "cholesteric", "thomson", "cube", "qtactoid",
        "wrap", "constrainedloop", "constrainedfunction",
    }
    toy_examples = {
        "inactive", "singleequalityconstraint", "twoinequalityconstraints",
    }

    print("=== Summary ===")
    for label, names in (("Mesh / field examples", mesh_examples), ("Toy constrained examples", toy_examples)):
        subset = [r for r in results if r.example in names and r.algorithm != "unconstrained"]
        if not subset:
            continue
        print(f"\n{label}")
        by_algo: Dict[str, List[RunMetrics]] = {}
        for r in subset:
            by_algo.setdefault(r.algorithm, []).append(r)
        for algo in ("penalty", "sqp", "pgd"):
            rows = by_algo.get(algo, [])
            if not rows:
                continue
            conv = sum(1 for r in rows if r.converged)
            times = [r.wall_s for r in rows if r.converged]
            iters = [r.total_iters for r in rows if r.converged and r.algorithm != "penalty"]
            outer = [r.penalty_outer for r in rows if r.converged and r.algorithm == "penalty"]
            inner = [r.inner_iters for r in rows if r.converged and r.algorithm == "penalty"]
            line = f"  {algo:8}  {conv}/{len(rows)} converged"
            if times:
                line += f"  time median {sorted(times)[len(times)//2]:.2f}s (total {sum(times):.1f}s)"
            if iters:
                line += f"  median {sorted(iters)[len(iters)//2]} outer iters"
            if outer:
                line += f"  median {sorted(outer)[len(outer)//2]} penalty outers, {sorted(inner)[len(inner)//2]} inner LBFGS steps"
            print(line)

    print("\nHead-to-head (converged runs only; penalty inner iters vs SQP/PGD outer iters)")
    groups = group_by_example(results)
    print(f"{'Example':<22} {'Penalty':<18} {'SQP':<18} {'PGD':<18} {'SQP/PGD speedup vs penalty time'}")
    print("-" * 95)
    for example, rows in groups.items():
        if example not in mesh_examples:
            continue
        by = {r.algorithm: r for r in rows if r.converged}
        if len(by) < 2:
            continue
        cols = []
        for algo in ("penalty", "sqp", "pgd"):
            r = by.get(algo)
            if not r:
                cols.append("-")
            elif algo == "penalty":
                cols.append(f"{r.penalty_outer}×/{r.inner_iters}i {r.wall_s:.2f}s")
            else:
                cols.append(f"{r.total_iters}it {r.wall_s:.2f}s")
        speed = ""
        if "penalty" in by and "sqp" in by and by["penalty"].wall_s > 0:
            ratio = by["sqp"].wall_s / by["penalty"].wall_s
            if ratio >= 1:
                speed = f"Penalty {ratio:.1f}× faster"
            else:
                speed = f"SQP {1/ratio:.1f}× faster"
        elif "penalty" in by and "pgd" in by and by["penalty"].wall_s > 0:
            speed = f"PGD {by['pgd'].wall_s / by['penalty'].wall_s:.1f}× slower"
        print(f"{example:<22} {cols[0]:<18} {cols[1]:<18} {cols[2]:<18} {speed}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", nargs="*", help="Example base names (e.g. loop nematic)")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of tables")
    parser.add_argument("--include-ignored", action="store_true", help="Include [CI:Ignore] tests")
    args = parser.parse_args(argv)

    paths = discover_tests(args.examples or None)
    if not args.include_ignored:
        paths = [p for p in paths if not parse_flags(p)[0]]

    if not paths:
        print("No tests matched.", file=sys.stderr)
        return 1

    print(f"Running {len(paths)} algorithm tests...", file=sys.stderr)
    results = [run_timed(p) for p in paths]

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print_table(results)
        print_summary(results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
