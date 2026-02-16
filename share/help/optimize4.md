[comment]: # (Optimize4 help)

# Optimize4
[tagOptimize4]: # (Optimize4)

The `optimize4` package is a new and more powerful optimization package for morpho. It implements a much wider variety of possible algorithms than the previous `optimize` package. 

The design is intended to be flexible, enabling customization of the choice of algorithm and easy incorporation of new algorithms by the developer or user. To use the package, simply import it into your morpho program as usual:

    import optimize4

The package provides three main kinds of class that work together:

* `OptimizationProblem` classes are used to describe a shape optimization problem to be solved.
* `OptimizationAdapter` provide a uniform interface for optimization, setting and getting parameters and evaluating gradients etc. `OptimizationAdapter`s can also be used to transform one type of problem to another, e.g. a constrained problem to an unconstrained problem, facilitating the use of different optimization algorithms. 
* `OptimizationController` classes implement an optimization algorithm or a useful subcomponent. Controllers work with a provided `OptimizationAdapter` to evaluate necessary quantities and direct how parameters are to be adjusted as the algorithm proceeds. 

[showsubtopics]: # (subtopics)

## OptimizationAdapter
[tagOptimizationAdapter]: # (OptimizationAdapter)
[tagAdapter]: # (Adapter)

The `OptimizationAdapter` class defines a standard interface for optimization problems. Adapter objects evaluate the value and derivatives of the objective function, as well as any constraints present. `OptimizationAdapter` objects can be chained together, to convert the problem into a more convenient form or other helpful effects. 

An `OptimizationAdapter` implements the following methods: 

* `set(x)` - Sets the parameters, supplied as a `Matrix`.
* `get()`  - Retrieves the current parameters.
* `value()` - Returns the value of the objective function.
* `gradient()` - Returns the gradient of the objective function as a `Matrix`.
* `countConstraints()` - Returns the total number of constraints present. 
* `countEqualityConstraints()` - Returns the total number of equality constraints present. 
* `countInequalityConstraints()` - Returns the total number of inequality constraints present.
* `constraintValue()` - Returns a `List` of the values of the constraint functions. The list may contain values or `Matrix` objects with multiple values. 
* `constraintGradient()` - Returns a `List` of gradients of the constraint functions; each element is a `Matrix` with columns corresponding to the gradient of the constraint function.

An `OptimizationAdapter` may also provide second derivative information:

* `hessian()` - Returns the hessian of the objective function if available or `nil` otherwise. 
* `constraintHessian()` - Returns a List containing the hessians of any constraints.

[showsubtopics]: # (subtopics)

### DelegateAdapter
[tagDelegateAdapter]: # (DelegateAdapter)

A `DelegateAdapter` implements the `OptimizationAdapter` interface, but simply redirects all of method calls to an second adapter.

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

### ProxyAdapter
[tagProxyAdapter]: # (ProxyAdapter)

A `ProxyAdapter` implements a cache: Calls to `value()`, `gradient()`, and other methods are returned from the cache if they have already been calculated, or are calculated as necessary. Every time `set()` is called with new parameters, the cache is cleared. This adapter therefore prevents multiple evaluation of potentially expensive quantities like the gradient or the hessian by `OptimizationController`s. Using a `ProxyAdapter` helps simplify writing an `OptimizationController`: there's no need to temporarily store these quantities within the controller, for example.

A `ProxyAdapter` also keeps track of how many times the objective function value, gradient etc. are actually calculated. Print this information by calling the `report()` method:

    adapter.report()

You may retrieve the data as a `List` by calling the `countEvals()` method: 

    var count = adapter.countEvals()

The list is ordered as follows: `[no. value(), no. gradient(), no. hessian(), no. constraintValue(), no. constraintGradient(), no. constraintHessian()]` where each entry is the number of calls to the corresponding method. This information can be used, for example, to assess the performance of different algorithms on various problems for example. 

### DeflationAdapter
[tagDeflationAdapter]: # (DeflationAdapter)

A `DeflationAdapter` is used to implement the "deflation" method of solution landscape exploration. It modifies a problem by adding additional inequality constraints: 

    | x - xsoln |_2/R - 1 > 0 

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

### LagrangeMultiplierAdapter

### ReprojectionAdapter

### L1PenaltyAdapter
[tagL1PenaltyAdapter]: # (L1PenaltyAdapter)

An `L1PenaltyAdapter` is similar to a `PenaltyAdapter` but uses the 1-norm rather than the 2-norm. 

### FiniteDifferenceAdapter
[tagFiniteDifferenceAdapter]: # (FiniteDifferenceAdapter)

A `FiniteDifferenceAdapter` evaluates the gradient and hessian of the objective 

### FunctionAdapter

### ProblemAdapter

## OptimizationController 
[tagOptimizationController]: # (OptimizationController)

The `OptimizationController` is a base class for implementing optimization algorithms. It provides a number of useful generic methods for checking convergence, reporting information consistently, etc. Developers should refer to the associated manual; here we explain settings common to all `OptimizationController`s. 

Success of an optimization is typically assessed by comparing convergence criteria to target tolerances. You can adjust these by setting the relevant properties of an `OptimizationController`.

You can also control the level of output generated by the `OptimizationController`. To create an `OptimizationController` that suppresses output except for warnings and errors,

    var opt = OptimizationController(adapt, quiet=true)

More fine-grained control is available through the `verbosity` option. For example:

    var opt = OptimizationController(adapt, quiet="verbose")

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

### LineSearchController
[tagLineSearchController]: # (LineSearchController)

### DirectedLineSearchController

### WolfeLineSearchController

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

### BFGSController
[tagBFGSController]: # (BFGSController)

A `BFGSController` implements the Broyden–Fletcher–Goldfarb–Shanno (BFGS) algorithm for unconstrained optimization. BFGS is an example of a quasi-Newton method, offering superlinear convergence without the computational cost of evaluating the Hessian matrix. 

The method iteratively builds an approximation to the Hessian matrix; the approximation is updated at each iteration from available gradient information. 

As in the Newton method, the search direction `d` at each iteration is obtained by solving:

    H_BFGS.d = - g

where  g is the gradient of the objective function. Note that H\_BFGS is the BFGS estimate of the Hessian, rather than the Hessian itself. 

Having found the search direction, the `BFGSController` performs a linesearch in that direction. See `NewtonController` for additional options to control this process. 

### InvBFGSController

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

    var opt = LBFGSController(adapter, maxhistorylength=20)

Increasing the history length may improve the estimate of the inverse hessian at the expense of memory and work per iteration. The default value of 10 has been found sufficient for many applications.

### ProjectedGradientDescentController
[tagProjectedGradientDescentController]: # (ProjectedGradientDescentController)



### SQPController

### PenaltyController
[tagPenaltyController]: # (PenaltyController)


