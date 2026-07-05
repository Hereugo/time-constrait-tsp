# Graph Showcase App

This Streamlit app lives in its own folder and reads graph instances directly from the repository's `datasets/` directory.

It highlights the two special parts of your instances:

- each node has a reward value
- each edge has a weight / travel cost

## Features

- browse dataset collections such as `planar_weighted_small`
- browse nested dataset collections such as `euclidean_scenarios/ring`
- pick any graph instance file
- choose which result directory under `results/` to compare against
- explore the graph interactively with drag, zoom, hover, and spring physics
- view Euclidean complete-graph matrix datasets as fixed coordinate points without drawing every implied edge
- tune the physics solver, repulsion, spring length, and damping
- visualize node rewards with color and compact node sizes in Euclidean coordinate views
- load the matching solution from the selected result directory and overlay the chosen tour
- show edge weights directly on the graph
- inspect reward and edge tables
- view the raw dataset and raw solution files inside the app

## Run it

From inside `graph_showcase_app/`:

```bash
uv sync
uv run streamlit run app.py
```

Then open the local URL printed by Streamlit in your browser.

## Notes

- The app assumes the dataset format described in the main README:
  - first line: `n m`
  - second line: `n` node rewards
  - remaining `m` lines: `u v w`
- It also supports `TTSP_MATRIX` files generated for Euclidean complete-graph collections, including nested scenario folders.
- For Euclidean complete graphs with `# coord node x y` comments, the app uses fixed coordinates and overlays only the selected tour edges; the complete graph's other implied edges are hidden.
- For nested dataset collections, matching result directories use the collection path with `/` replaced by `_`, for example `datasets/euclidean_scenarios/ring` matches `results/euclidean_scenarios_ring_budget500`.
- matching solutions are resolved by filename inside the selected result directory, for example `results/planar_weighted_small_20/graph_094.txt`
- result directory names can encode parameter settings such as budgets or solver variants
- node `1` is highlighted because the problem statement uses it as the depot
- dependencies are now tracked by `uv` in `pyproject.toml` and `uv.lock`
- `requirements.txt` is still present as the original source list, but `uv sync` is the main setup path now

## Comparing GA Batches

Generate several GA result directories from the repository root:

```bash
python3 approaches/genetic/run_batches.py --input datasets/custom --budget 22 --seeds 1 2 3 --generations 100 --population-size 50
```

The runner writes normal solution files under `results/` and GA metadata under `results_metadata/genetic/`. Result directory names start with the dataset collection name, so the app lists them for that collection. Open the `Run comparison` tab to compare reward, cost, route hops, and validation status for the currently selected graph.
