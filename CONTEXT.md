# Time-Constrained TSP

This context describes the routing language used in the thesis and implementation for the Time-Constrained Traveling Salesman Problem variant studied in this repository.

## Language

**Time-Constrained Traveling Salesman Problem (TTSP)**:
A routing problem where a route starts and ends at a depot, visits reward-bearing nodes, and must stay within a fixed travel budget while maximizing collected reward.
_Avoid_: Refueling variant, standard TSP

**Depot**:
The fixed start and end point of every route.
_Avoid_: Start node, home node

**Reward**:
The value associated with visiting a node, collected at most once per route.
_Avoid_: Profit, prize, value

**Travel Budget**:
The maximum total travel cost allowed for a route.
_Avoid_: Fuel capacity, time limit when discussing the implemented non-refueling problem

**Tour**:
A depot-starting, depot-ending route used to collect rewards within the travel budget. In this project language, a tour may traverse graph nodes as part of shortest-path connections between selected nodes.
_Avoid_: Simple cycle when repeated vertices are possible

**Greedy Baseline**:
A constructive heuristic used as the first comparison point for more advanced heuristics.
_Avoid_: Exact solver, approximation algorithm

**Genetic Algorithm**:
A population-based heuristic that searches over candidate tour-building priorities and evaluates the feasible tours produced from them.
_Avoid_: Exact solver, standard TSP genetic algorithm

## Example Dialogue

Developer: Does the greedy baseline collect the reward of the depot?

Domain expert: No. The depot is only the fixed start and end point; rewards are collected from visited non-depot nodes.

Developer: If the tour connects two selected nodes through a shortest path, do intermediate nodes count as visited?

Domain expert: Yes. Any non-depot node traversed by the expanded tour contributes its reward at most once.
