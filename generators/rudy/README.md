# Rudy Graph Generator

`rudy` is a small command-line graph generator written in C. It produces
weighted undirected graphs and prints them as plain text to standard output.

This folder contains:

- `rudy.c`: the generator and command-line interface
- `gb_lib.c`: graph-building support code
- `ggenerator.readme`: the original historical note that came with the source

## Build

From this directory:

```bash
gcc gb_lib.c rudy.c -lm -o rudy
```

This produces an executable named `rudy`.

## Basic Usage

```bash
./rudy <graph_expression>
```

If you run `./rudy` with no arguments, it prints the built-in help text.

## Output Format

Most commands print a graph in this format:

```text
n m
u1 v1 w1
u2 v2 w2
...
```

- `n`: number of vertices
- `m`: number of edges
- each remaining line is `u v w`
- vertices are numbered from `1`
- `w` is the edge weight

Example:

```bash
./rudy -clique 4
```

Output:

```text
4 6
1 4 3
1 3 2
1 2 1
2 4 2
2 3 1
3 4 1
```

## How Expressions Work

`rudy` uses Reverse Polish Notation (RPN), which means it works like a stack.

- a graph generator pushes a graph onto the stack
- a unary operator modifies the graph on top of the stack
- a binary operator combines the top two graphs on the stack
- the command is valid only if exactly one graph remains at the end

## Simple Graph Generators

These options create a graph:

- `-clique <size>`: complete graph on `size` vertices
- `-circuit <length>`: cycle graph on `length` vertices
- `-grid_2D <rows> <cols>`: 2D grid
- `-grid <size> <dimension>`: cubic grid in higher dimensions
- `-toroidal_grid_2D <rows> <cols>`: wrapped 2D grid
- `-toroidal_grid <size> <dimension>`: wrapped higher-dimensional grid
- `-leap_2D <rows> <cols> <move_type>`: 2D leap graph
- `-leap <size> <dimension> <move_type>`: higher-dimensional leap graph
- `-wrapped_leap_2D <rows> <cols> <move_type>`: wrapped 2D leap graph
- `-wrapped_leap <size> <dimension> <move_type>`: wrapped higher-dimensional leap graph
- `-simplex <sum> <dimension>`: simplex graph
- `-bounded_simplex <sum> <dimension> <bound>`: simplex graph with coordinate bound
- `-planar <size> <density> <seed>`: random planar graph
- `-rnd_graph <size> <density> <seed>`: random graph
- `-spinglass2pm <rows> <cols> <percent_negative> <seed>`
- `-spinglass3pm <rows> <cols> <layers> <percent_negative> <seed>`
- `-spinglass2g <rows> <cols> <seed>`
- `-spinglass3g <rows> <cols> <layers> <seed>`

## Unary Operators

These consume one graph from the top of the stack and return one graph:

- `-random <low> <high> <seed>`: replace edge weights with random integer weights
- `-times <k>`: multiply all edge weights by `k`
- `-plus <k>`: add `k` to all edge weights
- `-complement`: replace the graph with its complement
- `-line`: replace the graph with its line graph

## Binary Operators

These consume the top two graphs on the stack:

- `+`: union of two graphs with the same number of vertices
- `x`: Cartesian product of two graphs
- `:`: join the two graphs by adding all edges between them

## Examples

Generate a 2D grid:

```bash
./rudy -grid_2D 3 5 > grid.txt
```

Generate a planar graph with 20 vertices and 40% density:

```bash
./rudy -planar 20 40 1 > planar.txt
```

Generate a clique, then assign random weights in `[10, 30]`:

```bash
./rudy -clique 5 -random 10 30 7 > weighted_clique.txt
```

Generate a cycle and scale every weight by `4`:

```bash
./rudy -circuit 5 -times 4 > scaled_cycle.txt
```

Take the Cartesian product of a clique and a grid:

```bash
./rudy -clique 3 -grid_2D 2 2 x > product.txt
```

Join a circuit and a clique:

```bash
./rudy -circuit 4 -clique 2 : > joined.txt
```

## Notes and Caveats

- `density` parameters are percentages in the range `0` to `100`.
- The graph output is undirected, so each edge is printed once.
- The `-spinglass*` commands are special one-shot generators and should be used by themselves.
- `-rnd_graph` currently appears unreliable in this checkout and may terminate with a panic error.
- The code is old and may compile with many warnings on modern compilers, even when the build succeeds.

## Quick Reference

```bash
./rudy -clique 10
./rudy -grid_2D 4 4
./rudy -planar 30 50 123
./rudy -clique 8 -random 1 20 42
./rudy -circuit 6 -times 3 -plus 2
./rudy -clique 3 -grid_2D 2 3 x
```
