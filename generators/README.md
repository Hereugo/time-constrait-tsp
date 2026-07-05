# Graph Instance Generator

## Euclidean Complete-Graph Matrix Generator

`generate_euclidean_matrix.py` generates synthetic Euclidean complete-graph TTSP instances in matrix format. The travel budget is not written to the dataset file; pass `L_max` to the algorithms with `--budget`.

```bash
python3 generators/generate_euclidean_matrix.py \
  --samples 100 \
  --nodes 50 \
  --output-dir datasets/euclidean_complete_small \
  --scenario uniform_center_depot \
  --seed-base 1000 \
  --coordinate-max 1000 \
  --reward-min 1 \
  --reward-max 100 \
  --include-reference-budget
```

Each generated file has the format:

```text
# coord 1 x y
# coord 2 x y
TTSP_MATRIX
n
r1 r2 r3 ... rn
w11 w12 w13 ... w1n
w21 w22 w23 ... w2n
...
wn1 wn2 wn3 ... wnn
```

- `n`: number of vertices, including depot node `1`
- `r1 ... rn`: reward for each node; `r1` is `0` for the depot
- `wij`: rounded Euclidean edge weight from node `i` to node `j`
- `# coord` comments: original generated coordinates, ignored by algorithms
- `# scenario`, `# geometry`, `# depot_position`, and `# reward_pattern`: generated experiment setup comments, ignored by algorithms
- `# reference_nearest_neighbor_tour_cost`: optional full-tour cost comment for choosing budgets, ignored by algorithms

Scenarios provide readable experiment setups. The default `uniform_random_depot` preserves the original uniformly sampled coordinates and uniform rewards, with depot node `1` sampled like every other point. Named scenarios make it clearer what pressure an experiment applies:

- `uniform_center_depot`: uniform coordinates with the depot near the center
- `uniform_corner_depot`: uniform coordinates with the depot near a corner
- `clustered_center_depot`: clustered coordinates with the depot near the center
- `clustered_offset_depot`: clustered coordinates with the depot placed inside one cluster
- `clustered_outliers`: clustered coordinates plus sparse outlier nodes
- `corridor`: coordinates stretched along a corridor with the depot near one end
- `ring`: coordinates around a ring with the depot near the center
- `reward_near_depot`: higher rewards closer to the depot
- `reward_far_from_depot`: higher rewards farther from the depot
- `reward_cluster_hotspot`: one cluster has higher rewards than the others

Scenario details can be overridden for focused experiments:

```bash
python3 generators/generate_euclidean_matrix.py \
  --samples 100 \
  --nodes 100 \
  --output-dir datasets/euclidean_clustered_hotspot \
  --scenario reward_cluster_hotspot \
  --clusters 5 \
  --hotspot-cluster 3 \
  --cluster-spread-ratio 0.06
```

Useful override options:

- `--geometry`: `uniform`, `clustered`, `clustered_outliers`, `corridor`, or `ring`
- `--depot-position`: `random`, `center`, `corner`, `near_cluster`, or `corridor_start`
- `--reward-pattern`: `uniform`, `near_depot`, `far_from_depot`, or `cluster_hotspot`
- `--clusters`: number of clusters for clustered geometries
- `--cluster-spread-ratio`: cluster standard deviation as a fraction of `coordinate_max`
- `--outlier-fraction`: fraction of non-depot nodes sampled uniformly in `clustered_outliers`
- `--corridor-width-ratio`: corridor width as a fraction of `coordinate_max`
- `--ring-radius-ratio`: mean ring radius as a fraction of `coordinate_max`
- `--ring-noise-ratio`: radial noise as a fraction of `coordinate_max`
- `--hotspot-cluster`: one-based cluster index receiving higher rewards

Run one generated collection with an explicit travel budget:

```bash
python3 approaches/greedy/index.py \
  --input datasets/euclidean_complete_small \
  --output results/euclidean_complete_small_500 \
  --budget 500
```

## Rudy Sparse-Graph Generator

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
