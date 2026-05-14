# Graph Instance Generator

`generate.sh` is a small wrapper around `generators/rudy/rudy`.

It generates one or more graph instance files by:

1. running Rudy with the graph expression you provide
2. keeping Rudy's original edge weights
3. generating one random reward value for each node

Each generated file has the format:

```text
n m
r1 r2 r3 ... rn
u v w
u v w
...
```

- `n`: number of vertices
- `m`: number of edges
- `r1 ... rn`: reward for each node, in node order
- `u v`: edge endpoints
- `w`: edge weight produced by Rudy

## Basic Usage

Run the script from the project root:

```bash
./generators/generate.sh --samples N [options] -- <rudy graph expression>
```

Important:

- everything before `--` is handled by `generate.sh`
- everything after `--` is passed directly to Rudy

## Examples

Generate 3 planar graph instances:

```bash
./generators/generate.sh -n 3 -- -planar 25 40 1
```

Generate 5 planar graphs and store them in a custom folder:

```bash
./generators/generate.sh -n 5 -o generators/my_graphs -- -planar 30 50 1
```

Generate graphs with node rewards in the range `[10, 25]`:

```bash
./generators/generate.sh -n 4 --reward-min 10 --reward-max 25 -- -planar 20 35 1
```

Generate different Rudy graphs by changing the Rudy seed per sample:

```bash
./generators/generate.sh -n 3 --graph-seed-base 100 -- -planar 25 40 __SEED__
```

In the example above:

- sample 1 uses Rudy seed `100`
- sample 2 uses Rudy seed `101`
- sample 3 uses Rudy seed `102`

## Output Files

By default, files are written to:

```text
generators/generated/
```

with names like:

```text
graph_001.txt
graph_002.txt
graph_003.txt
```

You can change the output directory and file prefix.

## Options

- `-n`, `--samples N`: number of graph instances to generate
- `-o`, `-d`, `--dir`, `--output-dir DIR`: directory where files will be written
- `--prefix NAME`: file name prefix, default is `graph`
- `--reward-seed-base SEED`: starting seed for reward generation
- `--graph-seed-base SEED`: starting seed used when replacing `__SEED__` in the Rudy expression
- `--reward-min VALUE`: minimum reward value
- `--reward-max VALUE`: maximum reward value
- `-h`, `--help`: print help

## Output Directory Examples

All of these are valid:

```bash
./generators/generate.sh -n 3 -o generators/out -- -planar 20 40 1
./generators/generate.sh -n 3 -d generators/out -- -planar 20 40 1
./generators/generate.sh --samples=3 --dir=generators/out -- -planar 20 40 1
./generators/generate.sh --samples=3 --output-dir=generators/out -- -planar 20 40 1
```

## Reward Seeds

Node rewards are deterministic for a fixed reward seed base.

If you run:

```bash
./generators/generate.sh -n 3 --reward-seed-base 2000 -- -planar 25 40 1
```

then the reward seeds used are:

- sample 1: `2000`
- sample 2: `2001`
- sample 3: `2002`

## Notes

- If `generators/rudy/rudy` does not exist yet, the script tries to compile it automatically.
- If you do not use `__SEED__` in the Rudy expression, every sample will use the same Rudy graph structure and only the node rewards will vary.
- `reward-min` must be less than or equal to `reward-max`.
