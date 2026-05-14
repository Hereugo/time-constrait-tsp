# Time Constraited Traveling Salesman Problem

- [x] Problem Description (Overlay / Conditions that we work in)
- [ ] Solutions:
    - [ ] Greedy Approach
    - [ ] Genetic Algorithm Approach
    - [ ] Local Search Optimizing Approach
- [ ] Dataset Generation
    - [x] Random Dataset Generator (i.e. rudy)
    - [ ] TSP Dataset and editting to have the solution be best and fit the problem description
    - [ ] Real World Dataset (if we can find one that fits the problem description)
    - [x] Visualizier (~receives a graph~ and a solution and visualizes it)
- [ ] Run Experiments
    - [ ] Generate datasets / random / TSP-editted 
    - [ ] Run the algorithms on the datasets and compare results
- [ ] Conclusion

## Problem Description

- A set of points
- Each point has a reward value associated with it.
- Given a time constraint, find a tour (a sequence of points to visit) that maximizes the total reward collected while ensuring that the total time taken does not exceed the given time constraint.

## Input Format

The first line of the input contains two integers n and m.
The second line contains n integers r1, r2, ..., rn, where ri is the reward value associated with point i.
The next m lines each contain three integers u, v, and w, representing an edge from point u to point v with a time cost of w.

## Output Format

The output should be a two lines containing the maximum total reward with total time taken and the sequence of points to visit in the tour.

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
max_reward total_time
p1 p2 ... pk
```

## Constraints

For now constraits are not defined we will figure out the constraints as we go along and implement the algorithms.
