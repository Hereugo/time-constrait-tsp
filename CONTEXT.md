# Time-Constrained TSP

This context describes the routing language used in the thesis and implementation for the Time-Constrained Traveling Salesman Problem variant studied in this repository.

## Language

**Time-Constrained Traveling Salesman Problem (TTSP)**:
A routing problem on an edge-weighted graph where a tour starts and ends at a depot, visits reward-bearing nodes, and must stay within a fixed travel budget while maximizing collected reward.
_Avoid_: Refueling variant, standard TSP, assuming a complete graph unless explicitly stated

**Edge Weight**:
The travel cost assigned to an edge in the graph and counted toward the tour's travel budget.
_Avoid_: Vertex reward, profit

**Depot**:
The fixed start and end point of every route.
_Avoid_: Start node, home node

**Reward**:
The value associated with visiting a non-depot node, possibly zero, collected at most once per route.
_Avoid_: Score, profit, prize, value

**Reward-Bearing Node**:
A non-depot node with positive reward.
_Avoid_: Required node, customer

**Travel Budget**:
The maximum total travel cost allowed for a route.
_Avoid_: Fuel capacity, time limit when discussing the implemented non-refueling problem

**Tour**:
A depot-starting, depot-ending route used to collect rewards within the travel budget. A tour may revisit nodes or edges; each non-depot reward is still collected at most once.
_Avoid_: Simple cycle, path, selected-node sequence

**Shortest-Path-Expanded Tour**:
A tour represented by selected nodes, where each consecutive selected-node pair is expanded using a shortest path in the original graph, and intermediate nodes collect reward at most once.
_Avoid_: Unrestricted graph walk, simple TSP cycle

**Problem Instance**:
A single input graph with depot, edge weights, node rewards, and a travel budget to solve under the TTSP rules.
_Avoid_: Solved instance when referring only to an included input

**Greedy Baseline**:
A constructive heuristic used as the first comparison point for more advanced heuristics.
_Avoid_: Exact solver, approximation algorithm

**Genetic Algorithm**:
A population-based heuristic that searches over candidate tour-building priorities and evaluates the feasible tours produced from them.
_Avoid_: Exact solver, standard TSP genetic algorithm

**Jsprit Heuristic**:
A reward-primary heuristic that uses jsprit to search over explicitly visited reward-bearing nodes, then reports a validated shortest-path-expanded tour under the TTSP rules.
_Avoid_: Jsprit Solver, exact TTSP solver

**Small-Instance Exact Solver**:
An exact comparison method used on small TTSP instances to compute the optimal reward and assess heuristic solution quality.
_Avoid_: Scalable solver, main heuristic, literature baseline

**Instance Size Class**:
A named dataset group used to compare TTSP behavior at different graph sizes, such as small, medium, and large.
_Avoid_: Difficulty level when referring only to graph size

**Graph Family**:
A named dataset group used to compare TTSP behavior across graph topologies, such as planar, dense, or grid-like graphs.
_Avoid_: Instance size class when referring to topology rather than node count

**Result Set**:
A collection of solutions produced by one approach under one experimental setup, including dataset collection, travel budget, algorithm parameters, and seed when applicable.
_Avoid_: Approach when referring to a concrete run, result directory

**Per-Instance Runtime**:
The elapsed wall-clock time needed to produce one solution for one problem instance under a fixed experimental setup, including instance loading and preprocessing but excluding result-file writing.
_Avoid_: Batch runtime, selected-seed runtime when referring to the cost of a best-of-N summary

**Best-of-N Seed Summary**:
A comparison summary for a stochastic approach that uses the strongest result among N seeded result sets for each comparable instance, with runtime reported as the combined per-instance runtime of all N seeds.
_Avoid_: Expected single-run performance, average run, selected-seed runtime

**Best-Known Reward**:
The highest valid reward found among comparable result sets for the same instance and travel budget when no optimal reward is available.
_Avoid_: Optimum, exact reward

## Example Dialogue

Developer: Does the greedy baseline collect the reward of the depot?

Domain expert: No. The depot is only the fixed start and end point; rewards are collected from visited non-depot nodes.

Developer: If the tour connects two selected nodes through a shortest path, do intermediate nodes count as visited?

Domain expert: Yes. Any non-depot node traversed by the expanded tour contributes its reward at most once.
