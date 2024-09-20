Optimization test suite
=======================

\adapter\ - Test adapter classes 
    penalty.morpho - Test PenaltyAdapter class 
    proxy.morpho - Test ProxyAdapter class 
    functionadapter\ - Test FunctionAdapter class functionality
        conscounterr.morpho - Incorrect initialization of a FunctionAdapter
        eqconstrained.morpho - Test equality constraints
        ineqconstrained.morpho - Test inequality constraints 
        unconstrained.morpho - Test an unconstrained problem

\constrained\
    lagrangemultiplier.morpho - Work in progress on lagrange multiplier approach
    penalty.morpho - Test penalty method on a simple constrained quadratic

\controller\ - Test OptimizationController base class
    controller.morpho - Test basic OptimizationController methods
    objectiveinfinite.morpho - Test situation where an objective is infinite

\examples\ - Should contain example problems 

\gradientdescent\ - Test gradient descent methods
    conjugategradient.morpho - CG on quadratic function
    constraint_error.morpho  - Test that a constrained problem generates an error
    gradientdescent.morpho   - Direct descent on a simple quadratic
    linesearch.morpho        - Line searches on a simple quadratic 
    wolfe.morpho             - Wolfe line searches on a simple quadratic

\meshpenalty\ 
    loop.morpho - Mesh penalty method 

\newton\ - Newton and quasinewton methods 
    bfgs.morpho      - Test BFGSController on simple quadratic form
    bfgsinv.morpho   - Test BFGSInvController on simple quadratic form
    lbfgs.morpho     - Test LBFGSController on simple quadratic form
    newton.morpho    - Test NewtonController on simple quadratic form
    quadratic.morpho - Class for quadratic forms 

\penalty\ - Penalty examples

\problemadapter\ - ProblemAdapter

\unconstrained\
    testfunctions.morpho - Tests optimization of a collection of functions with several algorithms