[comment]: # (Optimize4 help)

# Optimize4
[tagOptimize4]: # (Optimize4)

The `optimize4` package is a new and more powerful optimization package for morpho. It implements a much wider variety of possible algorithms than the previous `optimize` package.

The design is intended to be flexible, enabling customization of the choice of algorithm and easy incorporation of new algorithms by the developer or user. To use the package, simply import it into your morpho program as usual:

    import optimize4

The package provides three main kinds of class that work together:

* `OptimizationProblem` classes are used to describe a shape optimization problem to be solved.
* `OptimizationAdapter` objects provide a uniform interface for optimization, setting and getting parameters and evaluating gradients etc. `OptimizationAdapter`s can also be used to transform one type of problem to another, e.g. a constrained problem to an unconstrained problem, facilitating the use of different optimization algorithms.
* `OptimizationController` classes implement an optimization algorithm or a useful subcomponent. Controllers work with a provided `OptimizationAdapter` to evaluate necessary quantities and direct how parameters are to be adjusted as the algorithm proceeds.

A typical workflow for a morpho problem is:

    var problem = OptimizationProblem(mesh)
    problem.addEnergy(someFunctional)
    problem.addConstraint(anotherFunctional)

    var adapter = ProblemAdapter(problem, mesh)
    var opt = LBFGSController(adapter)   // or SQPController(adapter) if constrained
    opt.optimize(500)

To optimize a **field** (or mesh and field together), pass one or more `Mesh` / `Field` targets to `ProblemAdapter`:

    var adapter = ProblemAdapter(problem, field)
    var adapter = ProblemAdapter(problem, mesh, field)   // coupled shape + field

Field terms in the objective or constraints must supply a `fieldgradient(field, mesh)` method on the functional, and declare which field they depend on via a `field` property (see `ProblemAdapter` below).

[showsubtopics]: # (subtopics)

## OptimizationProblem
[tagOptimizationProblem]: # (OptimizationProblem)

An `OptimizationProblem` is a container that describes an optimization problem in terms of morpho functionals. It holds a reference mesh, optional fields, a list of energies that make up the objective function, and global and local constraints.

Create a problem with a mesh:

    var problem = OptimizationProblem(mesh)

[showsubtopics]: # (subtopics)

### Adding energies
[tagaddEnergy]: # (addEnergy)

Use `addEnergy` to add a term to the objective function. The method returns an `Energy` object that can be modified after creation (for example, to set a `selection` or `prefactor`):

    var en = problem.addEnergy(functional, selection=nil, prefactor=nil)

The legacy names `addenergy`, `addconstraint`, and `addlocalconstraint` still work and forward to these methods.

The total objective is the sum of all energy terms. Each energy wraps a morpho functional and evaluates it via `functional.total(mesh)` (and `functional.gradient` when gradients are required).

### Adding constraints
[tagaddConstraint]: # (addConstraint)
[tagaddLocalConstraint]: # (addLocalConstraint)

Global constraints are added with `addConstraint`. The constraint value is the total of the functional over the mesh (optionally restricted by a `selection`), minus an automatic target computed at the time the constraint is added:

    var cons = problem.addConstraint(functional, selection=nil, field=nil)

Local constraints apply at mesh elements (for example, a level-set constraint at each vertex). Use `addLocalConstraint`:

    var cons = problem.addLocalConstraint(functional, selection=nil, field=nil,
                                          onesided=false, target=0)

Set `onesided=true` for inequality constraints of the form c(x) <= 0. Equality constraints are the default.

The returned `Constraint` objects expose `functional`, `target`, `selection`, `field`, and `onesided` properties.

Set `field=` on a constraint when the functional depends on a particular `Field` (used when updating the problem after mesh refinement; see below).

### Updating after refinement

After `MeshRefiner` or similar operations, call `problem.update(dict)` with a dictionary mapping old mesh/fields/selections to new ones. The problem mesh, attached fields, and functional field references are updated in place:

    var refmap = ref.refine(selection=srefine)
    problem.update(refmap)
    mesh = refmap[mesh]
    field = refmap[field]

## OptimizationAdapter
[tagOptimizationAdapter]: # (OptimizationAdapter)
[tagAdapter]: # (Adapter)

The `OptimizationAdapter` class defines a standard interface for optimization problems. Adapter objects evaluate the value and derivatives of the objective function, as well as any constraints present. `OptimizationAdapter` objects can be chained together, to convert the problem into a more convenient form or other helpful effects.

An `OptimizationAdapter` implements the following methods:

* `set(x)` - Sets the parameters, supplied as a `Matrix`.
* `get()`  - Retrieves the current parameters.
* `value()` - Returns the value of the objective function.
* `gradient()` - Returns the gradient of the objective function as a `Matrix`.
* `directionalDerivative(d)` - Directional derivative (g . d), a default implementation computes this dot product directly. Required for nondifferentiable merit functions (`L1PenaltyAdapter`).
* `countConstraints()` - Returns the total number of constraints present.
* `countEqualityConstraints()` - Returns the total number of equality constraints present.
* `countInequalityConstraints()` - Returns the total number of inequality constraints present.
* `constraintValue()` - Returns a `List` of the values of the constraint functions. The list may contain values or `Matrix` objects with multiple values. Inactive one-sided local constraints are zeroed in this list.
* `constraintGradient()` - Returns a `List` of gradients of the constraint functions; each element is a `Matrix` with columns corresponding to the gradient of the constraint function.

An `OptimizationAdapter` may also provide second derivative information:

* `hessian()` - Returns the hessian of the objective function if available or `nil` otherwise.
* `constraintHessian()` - Returns a List containing the hessians of any constraints.

[showsubtopics]: # (subtopics)

### ProblemAdapter
[tagProblemAdapter]: # (ProblemAdapter)

A `ProblemAdapter` is the main adapter for morpho shape optimization problems. It connects an `OptimizationProblem` to the `OptimizationAdapter` interface, reading and writing degrees of freedom from one or more `Mesh` or `Field` targets.

    var adapter = ProblemAdapter(problem, mesh)
    var adapter = ProblemAdapter(problem, field)           // field-only
    var adapter = ProblemAdapter(problem, mesh, field)     // stacked DOFs: mesh then field
    var adapter = ProblemAdapter(problem, f1, f2)          // multiple fields

**Parameter vector.** The target degrees of freedom are represented using a single column vector; these are concatenated in target order.

**Energies and constraints.** The adapter:

* Sums all energies for `value()`.
* Accumulates gradients per target from `functional.gradient(mesh)` (mesh targets) and `functional.fieldgradient(field, mesh)` (field targets).
* Routes field gradients only when the functional's `field` property matches the target (or lists it).
* Evaluates global and local constraints; splits equality vs one-sided inequality contributions in `constraintValue()` / `constraintGradient()`.
* Infers the mesh grade of functionals when `functional.grade` is absent (e.g. line/area/volume integrals).
* Does not provide a Hessian; use quasi-Newton controllers such as `LBFGSController` or `SQPController`.

**Field indexing.** `selectionToIndexList(selection, target)` maps a `Selection` to linear indices in the adapter parameter vector—for use with `FixAdapter`. Works for `Mesh` and `Field` targets; with multiple targets, indices are offset automatically. For vector-valued fields, pass `components=` to restrict which components are fixed:

    var fix = adapter.selectionToIndexList(bnd, field)
    var fix = adapter.selectionToIndexList(bnd, field, components=[0])  // x-component only
    var fadapt = FixAdapter(adapter, fix)

**Active set.** `constraintValueForActiveSet()` exposes raw local inequality values (including feasible u > 0) for constrained controllers. `LagrangeMultiplierAdapter`, `ProjectedGradientDescentController`, and `SQPController` use this for active-set logic.

Helper methods: `count()`, `energies()`, `constraints()`, `localConstraints()`, `selectionToIndexList`.

### FunctionAdapter
[tagFunctionAdapter]: # (FunctionAdapter)

A `FunctionAdapter` wraps plain morpho functions in the `OptimizationAdapter` interface. It is useful for general optimization tasks.

    var adapt = FunctionAdapter(fn (x) x[0]^2 + x[1]^2,
                                gradient=fn (x) Matrix([2*x[0], 2*x[1]]),
                                start=Matrix([1, 1]))

If `gradient` or `hessian` are omitted, finite-difference versions are constructed automatically (shared centered-difference kernels). Constraints are supplied as lists of functions, with optional `constraintgradients`, `constrainthessians`, and `equalitycount` (the number of leading constraints treated as equalities; the remainder are inequalities). The default `directionalDerivative(d)` uses the objective gradient when available.

### DelegateAdapter
[tagDelegateAdapter]: # (DelegateAdapter)

A `DelegateAdapter` implements the `OptimizationAdapter` interface, but simply redirects all of method calls to a second adapter.

Initialize the `DelegateAdapter` with the adapter to redirect to:

    var adapt = DelegateAdapter(targetAdapter)

### DeconstrainAdapter
[tagDeconstrainAdapter]: # (DeconstrainAdapter)

A `DeconstrainAdapter` converts a constrained problem to an unconstrained problem by ignoring the constraints. Calls to `countConstraints()` and similar methods always return `0`; calling `constraintValue()` and `constraintGradient()` return `nil`.

This class is used to simplify access to the objective function without the presence of constraints, typically for use with another adapter or for use with a controller class that does not accept a constrained problem.

### FixAdapter
[tagFixAdapter]: # (FixAdapter)

A `FixAdapter` holds the values of selected variables constant. Calls to `set()` do not change the values of the fixed variables, and the corresponding elements of `gradient()` and `constraintGradient()` are set to zero. This adapter does not support hessians.

Initialize the `FixAdapter` with a `List` of variables to be fixed:

    var fadapt = FixAdapter(adapt, [0,1,2])

With a `ProblemAdapter`, use `selectionToIndexList` to obtain correct variable indices from a mesh or field selection:

    var fix = adapter.selectionToIndexList(selection, mesh)
    var fix = adapter.selectionToIndexList(selection, field)
    var fadapt = FixAdapter(adapter, fix)

### ProxyAdapter
[tagProxyAdapter]: # (ProxyAdapter)

A `ProxyAdapter` implements a cache: Calls to `value()`, `gradient()`, and other methods are returned from the cache if they have already been calculated, or are calculated as necessary. Every time `set()` is called with new parameters, the cache is cleared. This adapter therefore prevents multiple evaluation of potentially expensive quantities like the gradient or the hessian by `OptimizationController`s. Using a `ProxyAdapter` helps simplify writing an `OptimizationController`: there's no need to temporarily store these quantities within the controller, for example.

`OptimizationController` automatically wraps adapters in a `ProxyAdapter` unless one is already present.

A `ProxyAdapter` also keeps track of how many times the objective function value, gradient etc. are actually calculated. Print this information by calling the `report()` method:

    adapter.report()

You may retrieve the data as a `List` by calling the `countEvals()` method:

    var count = adapter.countEvals()

The list is ordered as follows: `[no. value(), no. gradient(), no. hessian(), no. constraintValue(), no. constraintGradient(), no. constraintHessian()]` where each entry is the number of calls to the corresponding method. This information can be used, for example, to assess the performance of different algorithms on various problems for example.

### DeflationAdapter
[tagDeflationAdapter]: # (DeflationAdapter)

A `DeflationAdapter` is used to implement the "deflation" method of solution landscape exploration. It modifies a problem by adding additional inequality constraints:

    norm(x - xsoln) / R - 1 > 0

where `xsoln` is a previous solution to the optimization problem, and `R` is a deflation radius. The intent of the constraint is to prevent the optimizer reconverging on a previously known solution. The deflation radius is a metaparameter of the algorithm and must be tuned to the problem.

Initialize a `DeflationAdapter` with a target adapter and deflation radius:

    var dadapt = DeflationAdapter(adapter, radius=1)

Add a solution to the adapter:

    dadapt.addSolution(x) // typically use x = adapter.get()

A common strategy to move off a previous solution is to add random noise to the solution; a method to do so is provided:

    dadapt.jiggle(eps=0.1) // adds random gaussian noise with S.D. 0.1

### PenaltyAdapter
[tagPenaltyAdapter]: # (PenaltyAdapter)

A `PenaltyAdapter` is used to convert a constrained problem into an unconstrained problem where the constraints are incorporated into a modified objective function:

    f(x) = f_old(x) + mu |c|^2 + mu |d-|^2

where c is the value of the equality constraint functions and |d-| is the value of active inequality constraints (i.e. only those that have negative values). The parameter `mu` is called the *penalty parameter* and effectively penalizes the deviation of the solution from the constraint.

Initialize a `PenaltyAdapter` with a given initial penalty:

    var padapt = PenaltyAdapter(targetAdapter, penalty=1)

The penalty can be changed with `setPenalty(mu)` and read with `penalty()`. The adapter also provides `directionalDerivative(d)` for use in line searches.

If a Hessian is required, the underlying adapter must supply `hessian()` and `constraintHessian()`.

### LagrangeMultiplierAdapter
[tagLagrangeMultiplierAdapter]: # (LagrangeMultiplierAdapter)

A `LagrangeMultiplierAdapter` augments the optimization variables with Lagrange multipliers, forming the Lagrangian

    L(x, lambda) = f(x) - lambda · c(x)

where inactive inequality constraints have their multipliers set to zero. The combined parameter vector stacks `x` and `lambda` (see `lagrangeMultipliers()` / `setLagrangeMultipliers(lambda)`).

    var ladapt = LagrangeMultiplierAdapter(adapter)

Key methods:

* `varGradient()` - gradient of the Lagrangian with respect to the original variables: ∇f - Cᵀ lambda.
* `lagrangeMultipliers()` / `setLagrangeMultipliers(lambda)` - get or set the multiplier vector.
* `activeConstraintValue()` / `activeConstraintGradient()` - constraints on the current active set (equalities plus violated or tight inequalities, u <= 0).
* `activeConstraintSystem()` - returns `[values, gradients]` for the active set in one pass.
* `setActiveLagrangeMultipliers(lambda)` - update multipliers on the active set only.

This adapter is used internally by `SQPController` (as `control.ladapter` after `start()`).

### ReprojectionAdapter
[tagReprojectionAdapter]: # (ReprojectionAdapter)

A `ReprojectionAdapter` defines an unconstrained objective consisting only of the squared constraint violation:

    F(x) = |c|^2 + |d-|^2

It ignores the original objective and is used to drive the solution back toward the feasible set. `ProjectedGradientDescentController` and `SQPController` use it internally for reprojection steps via L-BFGS minimization of `F`.

### L1PenaltyAdapter
[tagL1PenaltyAdapter]: # (L1PenaltyAdapter)

An `L1PenaltyAdapter` is similar to a `PenaltyAdapter` but uses the 1-norm rather than the 2-norm:

    f(x) = f_old(x) + mu |c|_1 + mu |d-|_1

The resulting function is nondifferentiable, so `gradient()` and `hessian()` throw errors. Instead, use `directionalDerivative(d)` for line searches along direction `d`. This merit function is used by `ProjectedGradientDescentController` and `SQPController` during constrained line searches.

    var padapt = L1PenaltyAdapter(adapter, penalty=mu)
    padapt.directionalDerivative(direction)

### FiniteDifferenceAdapter
[tagFiniteDifferenceAdapter]: # (FiniteDifferenceAdapter)

A `FiniteDifferenceAdapter` wraps another adapter and supplies `gradient()` and `hessian()` by centered finite differences of `value()`, using appropriately scaled step sizes (the same kernels used when `FunctionAdapter` builds numerical derivatives).

    var fdadapt = FiniteDifferenceAdapter(adapter)

Only `value()` (and constraint methods, if present on the underlying adapter) need to be implemented on the wrapped adapter. This is useful when analytical derivatives are unavailable, but can be very expensive for large parameter vectors.


## OptimizationController
[tagOptimizationController]: # (OptimizationController)

The `OptimizationController` is a base class for implementing optimization algorithms. It provides a number of useful generic methods for checking convergence, reporting information consistently, etc.

**API naming:** compound **method** names use camelCase (`lineSearch`, `hasConverged`, `setPenalty`, `addEnergy`). **Optional arguments** at construction use all lowercase (`linesearch=`, `maxhistorylength=`, `recoverlinesearchfailure=`). Legacy `addenergy` / `addconstraint` / `addlocalconstraint` on `OptimizationProblem` still forward to the camelCase methods.

_Running an optimization_

Call `optimize(nsteps)` to run up to `nsteps` iterations. The method returns `true` if convergence criteria are met, `false` otherwise (including if a step fails or the iteration limit is reached without convergence).

Each iteration follows the sequence `begin()` → `step()` → `next()`, with `report(iter)` and `record()` called by `optimize`. Subclasses override these hooks to implement specific algorithms.

_Convergence tolerances_

Success is typically assessed via `hasConverged()`. The base class checks:

* `gradtol` (default `1e-6`) - stop when ||g|| < `gradtol`, where g is the gradient returned by `gradient()`.
* `etol` (default `1e-8`) - stop when the relative change in objective value between successive iterations falls below `etol`.
* `ctol` (default `1e-10`) - used by `PenaltyController` for constraint satisfaction.

Adjust tolerances on the controller instance:

    opt.gradtol = 1e-8
    opt.etol = 1e-10

Constrained controllers may override `hasConverged()` with additional criteria; see `SQPController` below.

_Verbosity_

You can control the level of output generated by the `OptimizationController`. To create an `OptimizationController` that suppresses output except for warnings and errors,

    var opt = OptimizationController(adapt, quiet=true)

More fine-grained control is available through the `verbosity` option. For example:

    var opt = OptimizationController(adapt, verbosity="verbose")

produces verbose output, which contains additional information useful for debugging. Possible options include:

* "verbose" - Detailed output
* "normal"  - Normal output, including the results at each iteration.
* "quiet"   - Suppresses output other than warnings and errors.
* "silent"  - Produces no output and doesn't raise warnings or errors. Use with caution.

[showsubtopics]: # (subtopics)

### GradientDescentController
[tagGradientDescentController]: # (GradientDescentController)

Implements the gradient descent algorithm with fixed stepsize, i.e. at each iteration the parameters are updated by some fixed fraction of the gradient:

    x_new = x_old - alpha*g

This is generally a toy algorithm; convergence is slow and not guaranteed. It is valuable for education and benchmarking purposes and occasionally useful for implementing other `OptimizationController`s.

Only appropriate for unconstrained problems.

### LineSearchController
[tagLineSearchController]: # (LineSearchController)

Extends `GradientDescentController` with a backtracking Armijo line search. Starting from unit stepsize, the step is reduced by factor `beta` (default `0.5`) until the sufficient decrease condition

    f(x + t d) < f(x) + alpha * t * (g · d)

is satisfied, with `alpha` defaulting to `0.2`. The accepted stepsize is stored in `stepsize`.

Options: `stepsize` (initial trial step), `alpha`, `beta`, `maxsteps` (default 50).

### DirectedLineSearchController
[tagDirectedLineSearchController]: # (DirectedLineSearchController)

Performs an Armijo line search along a fixed direction supplied at construction or via `setDirection(d)`. Uses `directionalDerivative(d)` on the adapter when available (required for nondifferentiable merit functions such as `L1PenaltyAdapter`).

`optimize(n)` performs a single line search only; `hasConverged()` always returns `false` so gradient-based stopping is not applied.

### WolfeLineSearchController
[tagWolfeLineSearchController]: # (WolfeLineSearchController)

Implements a strong Wolfe line search (Nocedal & Wright, Ch. 3). Parameters include `c1` (Armijo constant, default `1e-3`), `c2` (curvature constant, default `0.9`), `stepsize` (initial trial), and `steplimit`. Verbose debugging output is printed when the controller verbosity is `"verbose"`.

Can be passed to `NewtonController` as the `linesearch` argument:

    var opt = NewtonController(adapter, linesearch=WolfeLineSearchController)

### NewtonController
[tagNewtonController]: # (NewtonController)

Implements Newton's method, which is a rapidly converging method for unconstrained optimization where a Hessian is available. At each iteration, a search direction `d` is chosen by solving

    H.d = - g

Having found the search direction, the `NewtonController` performs a linesearch as described below.

While Newton's method converges rapidly from a good starting point, it can fail to converge from a poor one. It also requires hessian information, which is typically not available in `morpho` problems. Quasi-newton methods such as `LBFGSController` are hence recommended; these follow the same sequence as a `NewtonController`, but replace the hessian with an approximation.

The linesearch process can be controlled by the user. By default, a `NewtonController` creates a `LineSearchController` to perform the search, but you can supply your own. For example,

    var opt = NewtonController(adapter, linesearch=WolfeLineSearchController)

causes the `NewtonController` to create a `WolfeLineSearchController` to perform linesearches. You can control the settings of the linesearch by creating the controller yourself. This example performs a very loose linesearch by increasing `etol`:

    var ls = LineSearchController(adapter)
    ls.etol = 1e-4
    var opt = NewtonController(adapter, linesearch=ls)

### ConjugateGradientController
[tagConjugateGradientController]: # (ConjugateGradientController)

Implements nonlinear conjugate gradient with Fletcher–Reeves β and restarts when β < 0. Inherits line search behaviour from `NewtonController` but replaces the Newton direction with a conjugate gradient combination of the current and previous gradients.

Requires an unconstrained problem and uses only first derivatives.

### BFGSController
[tagBFGSController]: # (BFGSController)

A `BFGSController` implements the Broyden–Fletcher–Goldfarb–Shanno (BFGS) algorithm for unconstrained optimization. BFGS is an example of a quasi-Newton method, offering superlinear convergence without the computational cost of evaluating the Hessian matrix.

The method iteratively builds an approximation to the Hessian matrix; the approximation is updated at each iteration from available gradient information.

As in the Newton method, the search direction `d` at each iteration is obtained by solving:

    H_BFGS.d = - g

where g is the gradient of the objective function. Note that H_BFGS is the BFGS estimate of the Hessian, rather than the Hessian itself.

Having found the search direction, the `BFGSController` performs a linesearch in that direction. See `NewtonController` for additional options to control this process.

### InvBFGSController
[tagInvBFGSController]: # (InvBFGSController)

An `InvBFGSController` implements the BFGS algorithm, similar to `BFGSController`, except rather than estimating the hessian, it estimates the *inverse* hessian of the objective function instead. This leads to a more efficient algorithm, because an expensive linear solve

    H_BFGS.d = - g

can be replaced by a matrix multiply

    d = - invH_BFGS.g

Like a `BFGSController`, having found the search direction, the `InvBFGSController` performs a linesearch in that direction. See `NewtonController` for additional options to control this process.

The `InvBFGSController` is typically useful only for problems with a small number of parameters due to the need to maintain an explicit inverse hessian matrix. Use the `LBFGSController` for large problems.

### LBFGSController
[tagLBFGSController]: # (LBFGSController)

An `LBFGSController` implements the Limited-memory BFGS (LBFGS) algorithm for unconstrained optimization. In contrast to `InvBFGSController`, LBFGS does not store the estimated inverse hessian explicitly, but maintains a history of recent updates enabling it to find the search direction

    d = - invH_BFGS.g

by performing the matrix multiplication implicitly. Because it scales well with problem size, this is typically a preferred algorithm for unconstrained optimization.

In addition to the standard options for an `OptimizationController`, you can control the history length maintained when you create an `LBFGSController`:

    var opt = LBFGSController(adapter, maxhistorylength=20, recoverlinesearchfailure=true)

Increasing the history length may improve the estimate of the inverse hessian at the expense of memory and work per iteration. The default value of 10 has been found sufficient for many applications. Set `recoverlinesearchfailure=true` (default on `LBFGSController` and SR1 variants) to continue optimizing after a failed line search instead of stopping immediately.

### LSR1Controller
[tagLSR1Controller]: # (LSR1Controller)

`LSR1Controller` is the primary large-scale method: limited-memory *inverse* SR1 with line search. It can be used for both minimization, maximization and minimax (saddle-point) problems. 

Solve a regular minimization problem:

    var opt = LSR1Controller(adapt)

Solve a problem specifying variables to maximize, supplied as a collection of indices:

    var opt = LSR1Controller(adapter, maximize=[0, 1, 2, 3], maxhistorylength=10)

See `ProblemAdapter` and the `selectionToIndexList` method for information on how to obtain variable indices for shape optimization problems. 

Note that if `maximize` is set, a specialist merit function Φ = ½‖∇f‖² is used to measure progress. Control this with the optional argument `gradmerit`; the default is `true` when `maximize` is set. If `gradmerit` is false the regular objective function is used:

    var opt = LSR1Controller(adapter, gradmerit=false)

As for `LBFGSController`, you can pass a custom linesearch controller by setting `linesearch`; in this case `gradmerit` is ignored.

### TRSR1Controller
[tagTRSR1Controller]: # (TRSR1Controller)

`TRSR1Controller` is a trust region variant of the SR1 algorithm. It always uses grad merit Φ = ½‖∇f‖²: residual trust region on ½‖g + Bp‖², with grad-merit line-search fallback if the TR step is rejected. Intended for small or diagnostic saddle/root solves. Pass `cgMaxIters` and `cgTol` to tune the Steihaug CG subproblem.

    var opt = TRSR1Controller(adapter, maximize=[0], cgMaxIters=200, cgTol=1e-10)

Trust-region globalization is provided by composable controllers parallel to line search: `TrustRegionController` manages radius and step acceptance; `ResidualTrustRegionController` implements the residual model above.

### PenaltyController
[tagPenaltyController]: # (PenaltyController)

Implements the classical penalty method for constrained problems. The adapter is wrapped in a `PenaltyAdapter` and a sequence of unconstrained subproblems is solved with increasing penalty parameter μ. This is often a method of choice for constrained problems, particularly those with inequality constraints.

    var opt = PenaltyController(adapter, mu0=1, mumul=10.0,
                                subproblemmaxiterations=100,
                                controller=LBFGSController)

Options:

* `mu0` - initial penalty parameter (default `1`).
* `mumul` - factor by which μ is multiplied after each outer iteration (default `10`).
* `subproblemmaxiterations` - maximum iterations per subproblem (default `100`).
* `controller` - class used to solve each subproblem (default `LBFGSController`).

Convergence requires both the inner controller's `hasConverged()` and ||c||_1 < `ctol`. Outer iterations report `mu` and the constraint norm.

When using `PenaltyAdapter` directly (without `PenaltyController`), increase the penalty between solves with `setPenalty` and read it with `penalty()`:

    padapt.setPenalty(padapt.penalty() * 10)

### ProjectedGradientDescentController
[tagProjectedGradientDescentController]: # (ProjectedGradientDescentController)

Implements projected gradient descent for constrained problems:

1. Compute a search direction by removing the component of the gradient along **active** constraint normals (`activeConstraintGradient()`).
2. Line search using an `L1PenaltyAdapter` merit function with penalty `mu` (default `2`).
3. Reproject onto the feasible set by minimizing ||c||^2 with L-BFGS (`maxconstraintsteps` iterations, default `100`).

    var opt = ProjectedGradientDescentController(adapter, mu=2, steplimit=nil)

Optional `steplimit` caps the accepted line search step. Reprojection runs automatically at `start()` and after each `step()`. The reported `gradient()` is the last projected gradient.

### SQPController
[tagSQPController]: # (SQPController)

Implements Sequential Quadratic Programming for constrained problems The method models the objective function at each step as a quadratic form and enforces constraints during optimization through Lagrange multipliers. This is often a method of choice for constrained optimization, and is particularly effective where there are a few global equality constraints. 

Specifically, an SQPController:-

1. Maintains Lagrange multipliers via an internal `LagrangeMultiplierAdapter` (`control.ladapter` after `start()`).
2. Approximates the objective Hessian with L-BFGS on the unconstrained objective (`DeconstrainAdapter`).
3. Solves the KKT system for the active constraint set each step (Schur complement), with fallback to a pure L-BFGS step on ∇L if the system is singular.
4. Line searches along the primal direction using an adaptive L1 merit function.
5. Reprojects when constraint violation exceeds `feasol` (default `1e-5`).

    var opt = SQPController(adapter, penalty=1, maxconstraintsteps=100,
                            reprojecttol=1e-5, relgradtol=0.005,
                            relgraditers=20, stagtol=1e-2, lamcap=100)
    opt.optimize(500)

    print opt.ladapter.lagrangeMultipliers()

Key options:

* `feasol` / `reprojecttol` - tolerance on ||c||_1 for feasibility and reprojection triggering.
* `relgradtol`, `relgraditers` - stop if ||∇L|| falls below `relgradtol` times its initial value for `relgraditers` consecutive iterations.
* `stagtol` - alternative stop when the objective stagnates and ||∇L|| is moderate.
* `lamcap` - maximum allowed magnitude of Lagrange multipliers after least-squares sync on the active set.

Diagnostic methods:

* `kkt()` - assemble an explicit KKT matrix estimate (expensive; intended for small problems).
* `reproject()` - force a feasibility reprojection step.
