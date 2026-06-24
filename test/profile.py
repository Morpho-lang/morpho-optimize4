#!/usr/bin/env python3
"""Profile optimize4 algorithm tests with morpho6 -profile.

Strips Show() overhead by running lean harness scripts. Parses profiler
output and aggregates hotspots by category.

Usage:
  python3 test/profile.py
  python3 test/profile.py loop tactoid inactive
  python3 test/profile.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_ROOT = os.path.join(ROOT, "test")
TEST_BIN = os.path.join(TEST_ROOT, "bin")
COMMAND = "morpho6"

PROFILE_HEADER = re.compile(
    r"===Profiler output: Execution took ([\d.]+) seconds with (\d+) samples==="
)
PROFILE_LINE = re.compile(r"^(.+?)\s+([\d.]+)%\s+\[(\d+) samples\]")

# Representative mesh + toy cases; iteration caps match converged tests.
HARNESS = {
    "loop": {
        "import": 'import "test/examples/loop.morpho" for LoopExample',
        "build": "var example = LoopExample()\nvar adapt = example.build()",
        "sqp": ("SQPController(adapt, quiet=true)", "500"),
        "pgd": ("ProjectedGradientDescentController(adapt, quiet=true)", "10000"),
        "penalty": ("PenaltyController(adapt, quiet=true)", "20"),
    },
    "nematic": {
        "import": 'import "test/examples/nematic.morpho" for Nematic',
        "build": "var example = Nematic()\nvar adapt = example.build()",
        "sqp": ("SQPController(adapt, quiet=true)", "100"),
        "pgd": ("ProjectedGradientDescentController(adapt, quiet=true)", "1000"),
        "penalty": ("PenaltyController(adapt, quiet=true)", "20"),
    },
    "tactoid": {
        "import": 'import "test/examples/tactoid.morpho" for Tactoid',
        "build": "var example = Tactoid()\nvar adapt = example.build()",
        "sqp": ("SQPController(adapt, quiet=true)", "1000"),
        "pgd": ("ProjectedGradientDescentController(adapt, quiet=true)", "10000"),
        "penalty": ("PenaltyController(adapt, quiet=true)", "20"),
    },
    "constrainedloop": {
        "import": 'import "test/examples/constrainedloop.morpho" for ConstrainedLoop',
        "build": "var example = ConstrainedLoop()\nvar adapt = example.build()",
        "sqp": ("SQPController(adapt, quiet=true)", "500"),
        "pgd": ("ProjectedGradientDescentController(adapt, quiet=true)", "1000"),
        "penalty": ("PenaltyController(adapt, quiet=true)", "20"),
    },
    "inactive": {
        "import": 'import "test/examples/inactive.morpho"',
        "build": "var example = ConstrainedFunctionExample()\nvar adapt = example.build()\nadapt.set(Matrix([0.5, 0.1]))",
        "sqp": ("SQPController(adapt, quiet=true)", "25"),
        "pgd": ("ProjectedGradientDescentController(adapt, quiet=true)", "1000"),
        "penalty": ("PenaltyController(adapt, quiet=true)", "20"),
    },
}

OPT_PREFIXES = (
    "SQPController", "PenaltyController", "ProjectedGradientDescentController",
    "LBFGSController", "OptimizationController", "LineSearchController",
    "DirectedLineSearchController", "NewtonController", "BFGSController",
    "LagrangeMultiplierAdapter", "PenaltyAdapter", "L1PenaltyAdapter",
    "ReprojectionMixin", "ReprojectionAdapter", "ProxyAdapter",
    "ConstraintVectorMixin", "DeconstrainAdapter",
)

PROBLEM_PREFIXES = (
    "ProblemAdapter", "FunctionAdapter", "AreaEnclosed", "Length",
    "Mesh", "MeshBuilder",
)

OVERHEAD_KEYS = {
    "(garbage collector)", "system", "(global)",
    "Show.", "File.", "plotmesh",
}


@dataclass
class ProfileEntry:
    name: str
    pct: float
    samples: int


@dataclass
class ProfileResult:
    example: str
    algorithm: str
    wall_s: float
    total_samples: int
    entries: List[ProfileEntry] = field(default_factory=list)
    error: str = ""


def headless_env() -> dict:
    env = os.environ.copy()
    env["PATH"] = TEST_BIN + os.pathsep + env.get("PATH", "")
    return env


def categorize(name: str) -> str:
    for key in OVERHEAD_KEYS:
        if name.startswith(key) or name == key:
            return "overhead"
    for p in OPT_PREFIXES:
        if name.startswith(p):
            return "optimizer"
    for p in PROBLEM_PREFIXES:
        if name.startswith(p):
            return "problem"
    if name.startswith("Matrix.") or name.startswith("List.") or name.startswith("Range"):
        return "linear_algebra"
    return "other"


def make_script(example: str, algo: str) -> str:
    h = HARNESS[example]
    controller, nsteps = h[algo]
    return f"""import optimize4
{h["import"]}

{h["build"]}

var control = {controller}
control.optimize({nsteps})
"""


def parse_profile(raw: str) -> Tuple[float, int, List[ProfileEntry]]:
    wall_s = 0.0
    total_samples = 0
    entries: List[ProfileEntry] = []
    in_profile = False
    for line in raw.splitlines():
        hm = PROFILE_HEADER.search(line)
        if hm:
            wall_s = float(hm.group(1))
            total_samples = int(hm.group(2))
            in_profile = True
            continue
        if not in_profile:
            continue
        if line.strip() == "===":
            break
        m = PROFILE_LINE.match(line.strip())
        if m:
            entries.append(ProfileEntry(m.group(1), float(m.group(2)), int(m.group(3))))
    return wall_s, total_samples, entries


def run_profile(example: str, algo: str) -> ProfileResult:
    code = make_script(example, algo)
    proc = subprocess.run(
        [COMMAND, "-profile", "-e", code],
        cwd=ROOT,
        env=headless_env(),
        capture_output=True,
        text=True,
    )
    raw = (proc.stdout or "") + (proc.stderr or "")
    wall_s, total_samples, entries = parse_profile(raw)
    err = ""
    if proc.returncode != 0:
        err = f"exit {proc.returncode}"
    if not entries:
        err = err or "no profile output"
    return ProfileResult(example, algo, wall_s, total_samples, entries, err)


def bucket_summary(entries: Sequence[ProfileEntry]) -> Dict[str, float]:
    buckets: Dict[str, float] = {}
    for e in entries:
        buckets[categorize(e.name)] = buckets.get(categorize(e.name), 0.0) + e.pct
    return buckets


def top_optimizer(entries: Sequence[ProfileEntry], n: int = 8) -> List[ProfileEntry]:
    opt = [e for e in entries if categorize(e.name) == "optimizer"]
    return sorted(opt, key=lambda e: e.pct, reverse=True)[:n]


def print_result(r: ProfileResult) -> None:
    print(f"\n=== {r.example} / {r.algorithm} ({r.wall_s:.3f}s, {r.total_samples} samples) ===")
    if r.error:
        print(f"  ERROR: {r.error}")
        return
    buckets = bucket_summary(r.entries)
    print("  Time share:")
    for k, v in sorted(buckets.items(), key=lambda kv: kv[1], reverse=True):
        print(f"    {k:16} {v:5.1f}%")
    print("  Top optimizer hotspots:")
    for e in top_optimizer(r.entries):
        print(f"    {e.pct:5.2f}%  {e.name}")


def print_cross_cut(results: Sequence[ProfileResult]) -> None:
    print("\n=== Cross-cutting optimizer hotspots (mean % across runs) ===")
    acc: Dict[str, List[float]] = {}
    for r in results:
        if r.error:
            continue
        for e in r.entries:
            if categorize(e.name) != "optimizer":
                continue
            acc.setdefault(e.name, []).append(e.pct)
    ranked = sorted(acc.items(), key=lambda kv: sum(kv[1]) / len(kv[1]), reverse=True)
    for name, pcts in ranked[:15]:
        print(f"  {sum(pcts)/len(pcts):5.2f}% avg  {name}  ({len(pcts)} runs)")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", nargs="*", help="Example names (default: all harness cases)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--algos", nargs="*", default=["sqp", "pgd", "penalty"])
    args = parser.parse_args(argv)

    examples = args.examples or list(HARNESS.keys())
    results: List[ProfileResult] = []
    for ex in examples:
        if ex not in HARNESS:
            print(f"Unknown example: {ex}", file=sys.stderr)
            return 1
        for algo in args.algos:
            if algo not in HARNESS[ex]:
                continue
            print(f"Profiling {ex}/{algo}...", file=sys.stderr)
            results.append(run_profile(ex, algo))

    if args.json:
        payload = []
        for r in results:
            payload.append({
                "example": r.example,
                "algorithm": r.algorithm,
                "wall_s": r.wall_s,
                "total_samples": r.total_samples,
                "error": r.error,
                "buckets": bucket_summary(r.entries),
                "top": [{"name": e.name, "pct": e.pct} for e in r.entries[:20]],
            })
        print(json.dumps(payload, indent=2))
    else:
        for r in results:
            print_result(r)
        print_cross_cut(results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
