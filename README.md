# morpho-optimize4

A flexible optimization framework for [Morpho](https://morpho-lang.org/), intended to replace the built-in `optimize` package in Morpho 0.6. It supports unconstrained and constrained shape optimization on meshes and fields, with a composable adapter architecture and a range of optimization algorithms.

## Installation

This package can be installed with the `morphopm` package manager. Run 

    morphopm install optimize4
    

from the Terminal app. 

## Quick start

The usual workflow is: define an `OptimizationProblem`, wrap it in a `ProblemAdapter`, and run an `OptimizationController`.

```morpho
import optimize4
import meshtools

// Mesh and problem
var mesh = LineMesh(fn (t) [2*cos(t), sin(t)], -Pi...Pi:Pi/20, closed=true)
var problem = OptimizationProblem(mesh)
problem.addenergy(Length())
problem.addconstraint(AreaEnclosed())

// Optimize
var adapter = ProblemAdapter(problem, mesh)
var opt = SQPController(adapter)
opt.optimize(500)
```

For unconstrained problems, use `LBFGSController` instead of `SQPController`.

A fuller version of the loop example (fixed enclosed area, minimal perimeter) lives in [`test/examples/loop.morpho`](test/examples/loop.morpho); [`test/sqp/loop.morpho`](test/sqp/loop.morpho) shows it solved with SQP.

## Architecture

Three layers work together:

| Layer | Role |
|-------|------|
| **`OptimizationProblem`** | Describes energies and constraints using Morpho functionals |
| **`OptimizationAdapter`** | Uniform interface: parameters, objective, gradients, constraints. Adapters can be chained (penalty, fixing variables, caching, etc.) |
| **`OptimizationController`** | Implements an algorithm (L-BFGS, SQP, PGD, …) using only the adapter interface |

This separation lets algorithms stay independent of meshes and functionals, and lets you transform problems (e.g. penalty methods, Lagrange multipliers) without rewriting the solver.

## Choosing a controller

| Problem | Recommended controller | Notes |
|---------|------------------------|-------|
| Unconstrained | `LBFGSController` | Default for mesh/field problems; scales to large DOF counts |
| Equality / inequality constraints | `SQPController` | Primary constrained solver; L-BFGS Hessian + active-set KKT |
| Constrained, feasibility emphasis | `ProjectedGradientDescentController` | Gradient projection + reprojection each step |
| Constrained, simple outer loop | `PenaltyController` | Repeated unconstrained solves with increasing penalty |
| Small black-box test functions | `FunctionAdapter` + `LBFGSController` or `SQPController` | Analytical or finite-difference derivatives |
| Education / debugging | `GradientDescentController`, `LineSearchController` | Fixed step or Armijo line search |

Constrained controllers require constraints on the adapter (via `addconstraint` / `addlocalconstraint`). Unconstrained controllers will error if constraints are present unless you wrap the adapter (e.g. `PenaltyAdapter`, `DeconstrainAdapter`).

## Examples and tests

Reference problems live under [`test/examples/`](test/examples/) (loop, thomson, cholesteric, nematic, tactoid, qtensor, …). The same problems are exercised under `test/sqp/`, `test/pgd/`, and `test/penalty/` with different controllers.

See [`test/README.md`](test/README.md) for the automated test runner, CI directives, and layout.

## Documentation

In-package help is in [`share/help/optimize4.md`](share/help/optimize4.md) (available through Morpho's help system after installation). It documents all public classes, adapters, and controllers.

A longer manual is in [`docs/manual.lyx`](docs/manual.lyx) (LyX source).

## Status

This package is **experimental**. The API and algorithms are still evolving ahead of the Morpho 0.6 release. Feedback and bug reports are welcome via GitHub issues.
