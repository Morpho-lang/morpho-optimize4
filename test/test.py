#!/usr/bin/env python3
# Automated tests for morpho-optimize4
#
# Runs .morpho files under test/ (excluding examples/ and old/) with morpho6.
# Extra printed output (iteration traces, etc.) is allowed unless the
# test is in exact mode. Show() still runs but morphoview is stubbed out
# via test/bin/morphoview on PATH (see headless_env()).
#
# CI directives (anywhere in the file as // comments):
#   [CI:Ignore]    - skip this test (known failure or too slow for routine CI)
#   [CI:Exact]     - require // expect: lines to appear in output, in order
#   [CI:Converged] - must finish without OptMaxIter / OptLnSrchStpsz / Error;
#                    optional // expect: lines are also checked when present
#   [CI:Smoke]     - must run without unexpected Error (optimizer warnings OK)
#
# Expectations (exact mode; also enabled when // expect: is present):
#   // expect: <line>           - output line must appear in order
#   print expr // expect: <line>
#   // expect error 'ErrorName' - Morpho error (stack trace ignored)
#
# Default mode by directory when no directive is given:
#   test/sqp, test/pgd, test/penalty, test/unconstrained  -> converged
#   otherwise                               -> exact if // expect: present, else smoke
#
# Usage (see test/README.md):
#   python3 test/test.py          # human-readable summary
#   python3 test/test.py -c       # CI mode
#   python3 test/test.py -w 4     # pass -w4 to morpho6
#   python3 test/test.py path...  # run matching tests only

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Sequence, Tuple

COMMAND = "morpho6"
EXT = "morpho"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_ROOT = os.path.join(ROOT, "test")
TEST_BIN = os.path.join(TEST_ROOT, "bin")
EXCLUDE_DIRS = {"examples", "old"}


def headless_env() -> dict:
    """Prepend test/bin so a no-op morphoview stub is found before the real binary."""
    env = os.environ.copy()
    env["PATH"] = TEST_BIN + os.pathsep + env.get("PATH", "")
    return env

ERR_TOKEN = "@error"
STK_TOKEN = "@stacktrace"

CI_IGNORE = re.compile(r"\[CI:\s*Ignore\s*\]", re.I)
CI_EXACT = re.compile(r"\[CI:\s*Exact\s*\]", re.I)
CI_CONVERGED = re.compile(r"\[CI:\s*Converged\s*\]", re.I)
CI_SMOKE = re.compile(r"\[CI:\s*Smoke\s*\]", re.I)

EXPECT_LINE = re.compile(r"//\s*expect:\s*(.*)\s*$", re.I)
EXPECT_INLINE = re.compile(r"//\s*expect:\s*(.*)\s*$", re.I)
EXPECT_ERROR = re.compile(r"//\s*expect\s+error\s+'([^']+)'\s*$", re.I)

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
ERROR_RE = re.compile(r"Error\s+'([^']+)'", re.I)
WARN_MAXITER = re.compile(r"Warning\s+'OptMaxIter'")
WARN_LNSRCH = re.compile(r"Warning\s+'OptLnSrchStpsz'")
PENALTY_ITER = "==Penalty iteration"


class Mode(Enum):
    IGNORE = auto()
    EXACT = auto()
    CONVERGED = auto()
    SMOKE = auto()


@dataclass
class TestSpec:
    path: str
    mode: Mode
    expected: List[str] = field(default_factory=list)


@dataclass
class TestResult:
    path: str
    mode: Mode
    passed: bool
    skipped: bool = False
    message: str = ""


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text).rstrip()


def simplify_error_line(line: str) -> str:
    m = ERROR_RE.search(line)
    if m:
        return f"{ERR_TOKEN}[{m.group(1)}]"
    return line


def simplify_stacktrace(line: str) -> str:
    if "at line" in line:
        return STK_TOKEN
    return line


def normalize_output(raw: str) -> List[str]:
    lines = []
    pending_error = False
    for raw_line in raw.splitlines():
        line = strip_ansi(raw_line)
        line = simplify_error_line(line)
        line = simplify_stacktrace(line)
        if line == STK_TOKEN:
            continue
        if line.startswith(ERR_TOKEN):
            pending_error = True
            lines.append(line)
            continue
        if pending_error and " in " in line:
            continue
        pending_error = False
        if line:
            lines.append(line)
    return lines


def parse_expectations(lines: Sequence[str]) -> List[str]:
    expected: List[str] = []
    for line in lines:
        m_err = EXPECT_ERROR.search(line)
        if m_err:
            expected.append(f"{ERR_TOKEN}[{m_err.group(1)}]")
            continue
        m = EXPECT_LINE.search(line)
        if m:
            expected.append(m.group(1).strip())
    return expected


def parse_mode(filepath: str, file_lines: Sequence[str]) -> Mode:
    text = "".join(file_lines)
    if CI_IGNORE.search(text):
        return Mode.IGNORE
    if CI_EXACT.search(text):
        return Mode.EXACT
    if CI_CONVERGED.search(text):
        return Mode.CONVERGED
    if CI_SMOKE.search(text):
        return Mode.SMOKE

    expected = parse_expectations(file_lines)
    if expected:
        return Mode.EXACT

    rel = os.path.relpath(filepath, TEST_ROOT)
    top = rel.split(os.sep)[0]
    if top in ("sqp", "pgd", "penalty", "unconstrained"):
        return Mode.CONVERGED
    return Mode.SMOKE


def load_spec(filepath: str) -> TestSpec:
    with open(filepath, encoding="utf8") as fh:
        lines = fh.readlines()
    mode = parse_mode(filepath, lines)
    expected = parse_expectations(lines)
    return TestSpec(path=filepath, mode=mode, expected=expected)


def discover(paths: Optional[Sequence[str]] = None) -> List[str]:
    if paths:
        files: List[str] = []
        for arg in paths:
            candidate = os.path.join(ROOT, arg) if not os.path.isabs(arg) else arg
            if os.path.isfile(candidate):
                files.append(os.path.abspath(candidate))
            elif os.path.isdir(candidate):
                files.extend(
                    glob.glob(os.path.join(candidate, "**", "*." + EXT), recursive=True)
                )
            else:
                files.extend(glob.glob(candidate, recursive=True))
        files = sorted({f for f in files if f.endswith("." + EXT)})
    else:
        files = sorted(glob.glob(os.path.join(TEST_ROOT, "**", "*." + EXT), recursive=True))

    out: List[str] = []
    for f in files:
        rel = os.path.relpath(f, TEST_ROOT)
        parts = rel.split(os.sep)
        if parts[0] in EXCLUDE_DIRS:
            continue
        out.append(f)
    return out


def match_expected_in_order(output: Sequence[str], expected: Sequence[str]) -> Tuple[bool, str]:
    if not expected:
        return True, ""
    j = 0
    for line in output:
        if j < len(expected) and line == expected[j]:
            j += 1
    if j == len(expected):
        return True, ""
    return False, f"matched {j}/{len(expected)} expected lines; next expected: {expected[j]!r}"


def is_penalty_test(filepath: str) -> bool:
    rel = os.path.relpath(filepath, TEST_ROOT)
    return rel.split(os.sep)[0] == "penalty"


def check_maxiter(output: Sequence[str], penalty: bool = False) -> Optional[str]:
    """Return an error message if OptMaxIter should fail the test, else None."""
    for i, line in enumerate(output):
        if not WARN_MAXITER.search(line):
            continue
        if penalty:
            rest = "\n".join(output[i + 1 :])
            if PENALTY_ITER in rest:
                continue  # inner sub-solve; outer penalty loop continued
        return "optimizer did not converge (OptMaxIter)"
    return None


def check_unexpected_errors(
    output: Sequence[str], expected_errors: Sequence[str]
) -> Tuple[bool, str]:
    allowed = {e.strip(f"{ERR_TOKEN}[")[:-1] for e in expected_errors}
    for line in output:
        if line.startswith(f"{ERR_TOKEN}["):
            name = line[len(ERR_TOKEN) + 1 : -1]
            if name not in allowed:
                return False, f"unexpected error {name!r}"
        m = ERROR_RE.search(line)
        if m and m.group(1) not in allowed:
            return False, f"unexpected error {m.group(1)!r}"
    return True, ""


def check_converged(
    output: Sequence[str], expected_errors: Sequence[str], *, penalty: bool = False
) -> Tuple[bool, str]:
    ok, msg = check_unexpected_errors(output, expected_errors)
    if not ok:
        return False, msg
    msg = check_maxiter(output, penalty=penalty)
    if msg:
        return False, msg
    text = "\n".join(output)
    if WARN_LNSRCH.search(text):
        return False, "linesearch failed (OptLnSrchStpsz)"
    return True, ""


def check_smoke(output: Sequence[str], expected_errors: Sequence[str]) -> Tuple[bool, str]:
    return check_unexpected_errors(output, expected_errors)


def morpho_command(workers: Optional[int] = None) -> List[str]:
    cmd = [COMMAND]
    if workers is not None:
        cmd.append(f"-w{workers}")
    return cmd


def run_morpho(command: List[str], filepath: str) -> Tuple[int, str]:
    tmp = filepath + ".out"
    try:
        with open(tmp, "w", encoding="utf8") as outfile:
            result = subprocess.run(
                command + [filepath],
                stdout=outfile,
                stderr=subprocess.STDOUT,
                cwd=ROOT,
                env=headless_env(),
            )
        with open(tmp, encoding="utf8") as fh:
            raw = fh.read()
        return result.returncode, raw
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def run_test(spec: TestSpec, command: List[str]) -> TestResult:
    rel = os.path.relpath(spec.path, ROOT)
    if spec.mode == Mode.IGNORE:
        return TestResult(rel, spec.mode, passed=True, skipped=True, message="ignored")

    returncode, raw = run_morpho(command, spec.path)
    output = normalize_output(raw)
    expected_errors = [e for e in spec.expected if e.startswith(ERR_TOKEN)]

    if spec.mode == Mode.EXACT:
        ok, msg = match_expected_in_order(output, spec.expected)
        if not ok:
            return TestResult(rel, spec.mode, False, message=msg)
        if returncode != 0:
            return TestResult(rel, spec.mode, False, message=f"non-zero exit code {returncode}")
        return TestResult(rel, spec.mode, True)

    if spec.mode == Mode.CONVERGED:
        ok, msg = check_converged(
            output, expected_errors, penalty=is_penalty_test(spec.path)
        )
        if not ok:
            return TestResult(rel, spec.mode, False, message=msg)
        non_error = [e for e in spec.expected if not e.startswith(ERR_TOKEN)]
        if non_error:
            ok, msg = match_expected_in_order(output, non_error)
            if not ok:
                return TestResult(rel, spec.mode, False, message=msg)
        if returncode != 0:
            return TestResult(rel, spec.mode, False, message=f"non-zero exit code {returncode}")
        return TestResult(rel, spec.mode, True)

    ok, msg = check_smoke(output, expected_errors)
    if not ok:
        return TestResult(rel, spec.mode, False, message=msg)
    if returncode != 0:
        return TestResult(rel, spec.mode, False, message=f"non-zero exit code {returncode}")
    return TestResult(rel, spec.mode, True)


def color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run morpho-optimize4 tests")
    parser.add_argument("-c", action="store_true", help="CI mode")
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        metavar="N",
        help="pass -w N to morpho6 (worker threads)",
    )
    parser.add_argument("paths", nargs="*", help="optional test files or globs")
    args = parser.parse_args(argv)

    command = morpho_command(args.workers)
    files = discover(args.paths if args.paths else None)
    if not files:
        print("No tests found.", file=sys.stderr)
        return 1

    passed = failed = skipped = 0
    failures: List[TestResult] = []
    log_path = os.path.join(TEST_ROOT, "FailedTests.txt")

    print("--Begin testing---------------------")
    if args.workers is not None:
        print(f"Using morpho6 -w{args.workers}")

    with open(log_path, "w", encoding="utf8") as log:
        for filepath in files:
            spec = load_spec(filepath)
            result = run_test(spec, command)
            rel = result.path

            if result.skipped:
                skipped += 1
                if not args.c:
                    print(f"{rel}: {color('Skipped', '33')} ({result.message})")
                continue

            if result.passed:
                passed += 1
                if not args.c:
                    label = result.mode.name.lower()
                    print(f"{rel}: {color('Passed', '32')} ({label})")
            else:
                failed += 1
                failures.append(result)
                if args.c:
                    print(f"::error file={rel}::{rel} failed: {result.message}")
                else:
                    print(f"{rel}: {color('Failed', '31')} ({result.mode.name.lower()})")
                    print(f"  {result.message}")
                print(f"{rel}: Failed — {result.message}", file=log)

    print("--End testing-----------------------")
    run_total = passed + failed
    print(f"{passed} passed, {failed} failed, {skipped} skipped ({run_total + skipped} total)")

    if failures and not args.c:
        print(f"Details written to {os.path.relpath(log_path, ROOT)}")

    if args.c and failed:
        return 1
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
