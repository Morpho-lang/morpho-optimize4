# Tests

## Layout

| Directory | Contents |
|-----------|----------|
| [`examples/`](examples/) | Reference problems (loop, thomson, cholesteric, saddle, …) — not run by the test runner |
| [`sqp/`](sqp/), [`pgd/`](pgd/), [`penalty/`](penalty/) | Same problems under different controllers |
| [`saddlepoint/`](saddlepoint/) | Saddle-point stationarity (`LSR1Controller`, `TRSR1Controller`; `block_ferronematic.morpho` for block Gauss–Seidel on ferronematic) |
| [`trustregion/`](trustregion/) | Trust-region minimization on example problems (quadratic, qtensor, …) |
| [`unconstrained/`](unconstrained/) | Unconstrained mesh/field examples |
| [`adapter/`](adapter/), [`controllers/`](controllers/) | Unit-style adapter and controller tests |
| [`controllers/newton/`](controllers/newton/) | BFGS, L-BFGS, Newton |
| [`old/`](old/) | Legacy scripts — excluded from the runner |

## Running tests

From the package root:

```bash
python3 test/test.py
python3 test/test.py -w 4      # pass -w4 to morpho6 (faster mesh ops)
python3 test/test.py -c        # CI mode (GitHub Actions annotations, exit 1 on failure)
python3 test/test.py sqp       # run one subdirectory
```

Or from `test/`:

```bash
python3 test.py
python3 test.py -w 8
```

The runner executes all `.morpho` files under `test/` except `examples/` and `old/`. Iteration traces and other extra output are allowed unless a test is in exact mode.

### Headless `Show()`

Test files may call `Show()` for interactive use. The runner prepends `test/bin` to `PATH` so a no-op `morphoview` stub is used instead of launching the viewer.

## Test modes

Tests are classified from comments in each `.morpho` file:

| Mode | How it is selected | Pass criterion |
|------|-------------------|----------------|
| **exact** | `// [CI:Exact]` or any `// expect:` line | Expected lines appear in output, in order |
| **converged** | `// [CI:Converged]`, or `test/sqp/`, `test/pgd/`, `test/penalty/`, `test/unconstrained/`, `test/saddlepoint/`, `test/trustregion/` | No terminal `OptMaxIter`, no terminal `OptLnSrchStpsz`, no unexpected `Error`. For `test/penalty/`, `OptMaxIter` on early inner sub-solves is allowed if the outer penalty loop continues. |
| **smoke** | `// [CI:Smoke]` | Runs without unexpected `Error` |
| **ignore** | `// [CI:Ignore]` | Skipped (known failures) |

Examples:

```morpho
// [CI:Ignore]     // skip in CI
// [CI:Converged]   // require optimizer convergence
// [CI:Exact]       // match // expect: lines only
// expect: 2
// expect error 'OptCons'
print x // expect: 1.25
```

Failures are logged to `test/FailedTests.txt`.

Archived augmented-Lagrangian controller experiments live under [`../archive/augmentedlagrangian/`](../archive/augmentedlagrangian/).
