# Time-Constrained Traveling Salesman Problem

- [x] Problem Description (Overlay / Conditions that we work in)
- [ ] Solutions:
  - [x] Greedy Approach
  - [x] Genetic Algorithm Approach
  - [x] Small-Instance Exact Solver
  - [x] Jsprit Heuristic
- [x] Compare Results
  - [x] Validate stored tours against datasets
  - [x] Compare greedy and genetic result sets
  - [x] Use exact results as a small-instance reference
- [ ] Dataset Generation
  - [x] Random Dataset Generator (i.e. rudy)
  - [ ] TSP Dataset and editting to have the solution be best and fit the problem description
  - [ ] Real World Dataset (if we can find one that fits the problem description)
  - [x] Visualizier (~receives a graph~ and a solution and visualizes it)
- [ ] Run Experiments
  - [ ] Generate datasets / random / TSP-editted
  - [ ] Run the algorithms on the datasets and compare results
- [ ] Conclusion

## Current Mission

This project studies the Time-Constrained Traveling Salesman Problem (TTSP) on sparse weighted graphs. A tour starts and ends at the depot, collects each non-depot reward at most once, and must stay within a fixed travel budget.

The implemented scope compares a fast Greedy Baseline, a Genetic Algorithm, and a Jsprit Heuristic. A Small-Instance Exact Solver is used only as a reference for small instances, where it provides optimal rewards for evaluating heuristic quality. Local search is no longer part of the project scope.

## Problem Description

- A set of points
- Each non-depot point has a reward associated with it.
- Given a travel budget, find a depot-starting, depot-ending tour that maximizes collected reward while ensuring that the total travel cost does not exceed the budget.

## Input Format

The first line of the input contains two integers n and m.
The second line contains n integers r1, r2, ..., rn, where ri is the reward associated with point i.
The next m lines each contain three integers u, v, and w, representing an edge from point u to point v with a time cost of w.

## Output Format

The output should be two lines containing the total collected reward with total travel cost and the sequence of points in the tour.

NOTE: The points are numbered from 1 to n. The tour should start and end at the same point, which is point 1.

## Example

input.txt

```
n m
r1 r2 ... rn
u1 v1 w1
...
um vm wm
```

output.txt

```
total_reward total_cost
p1 p2 ... pk
```

## Constraints

For now constraits are not defined we will figure out the constraints as we go along and implement the algorithms.

## Greedy Approach

The greedy solver in `approaches/greedy/index.py` builds a closed walk that starts and ends at node `1` while staying inside the travel budget. The idea is to keep inserting the node that gives the best reward increase per extra unit of travel cost.

The implementation first reads the graph, rewards, and budget. After that it runs Dijkstra from every node with `build_shortest_path_index()`. This gives three things for every pair of nodes:

1. The shortest distance between them.
2. The actual shortest path as a list of vertices.
3. A `Counter` describing which vertices appear on that path.

This preprocessing is important because the graph is not assumed to be complete. When the greedy algorithm connects two nodes in the tour, it really connects them through their shortest path in the original graph.

The main routine is `greedy_algorithm()`. It starts with the smallest possible cycle, `tour = [1]`, which means the depot loops back to itself with cost `0` and reward `0`. Then it repeatedly checks every node that is not already in the tour and tries to insert it into every edge of the current cycle.

If the current cycle contains an edge `(left, right)`, inserting a node `v` there changes the cost by:

`additional_cost = dist(left, v) + dist(v, right) - dist(left, right)`

If the new total cost would exceed the budget, that insertion is discarded immediately.

For every feasible insertion, the solver also estimates the new collected reward. This part is a little more subtle than just adding `rewards[v]`. Because each cycle edge is expanded into a shortest path, inserting one node can cause the final walk to pass through other reward-bearing nodes as well. The code handles that with `replace_segment_counts()`: it removes the node counts for the old segment `(left, right)` and adds the counts for the two new segments `(left, v)` and `(v, right)`. Then `collected_reward()` sums rewards for all visited nodes, counting each node only once and skipping the depot.

Once cost and reward are known, the candidate is scored by:

`reward_gain / additional_cost`

This is the greedy part of the algorithm. Among all feasible insertions, it picks the one with the highest reward-to-cost ratio. If two candidates have the same ratio, `candidate_priority()` breaks ties by preferring:

1. Higher reward gain.
2. Lower additional cost.
3. Smaller node id.

After the best insertion is chosen, the node is added to the tour, the running cost and reward are updated, and the search starts again on the new cycle. The loop stops when there is no remaining insertion that both fits the budget and increases the reward.

At the end, `expanded_walk()` converts the abstract cycle of selected tour nodes into the real walk in the original graph by concatenating the stored shortest paths between consecutive tour nodes. The solution is then validated with `walk_cost()` and `walk_reward()` to make sure the final walk matches the tracked totals before being written out.

In short, the greedy solution is an insertion heuristic:

1. Precompute shortest paths.
2. Start from the depot.
3. Try every possible positive-reward insertion.
4. Choose the best reward-per-cost insertion.
5. Stop when no feasible positive-gain insertion remains.

## Jsprit Heuristic

The jsprit solver in `approaches/jsprit` is a Java 21 Maven project that builds a reward-primary TTSP heuristic using `jsprit-core`. It models each non-depot reward-bearing node as an optional service, uses shortest-path distances as travel times/costs, and enforces the travel budget as the vehicle latest arrival time.

The internal jsprit objective optimizes explicitly visited reward-bearing nodes first and travel cost second. The reported solution is still expanded through shortest paths and validated under the same TTSP rules as greedy and GA, so intermediate nodes on expanded segments contribute to the reported reward. Per-instance metadata records both `explicit_reward` and `validated_reward`.

Build:

```sh
mvn -f approaches/jsprit/pom.xml package
```

Run one file:

```sh
java -jar approaches/jsprit/target/jsprit-heuristic.jar --input datasets/custom/graph_001.txt --budget 30 --seed 1 --iterations 2000
```

Run a dataset collection:

```sh
java -jar approaches/jsprit/target/jsprit-heuristic.jar \
  --input datasets/planar_weighted_small \
  --output results/planar_weighted_small_jsprit_budget030_seed001_i2000 \
  --metadata-output results_metadata/jsprit/planar_weighted_small_jsprit_budget030_seed001_i2000 \
  --budget 30 \
  --seed 1 \
  --iterations 2000
```
