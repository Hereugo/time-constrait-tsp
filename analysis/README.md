# Result Comparison

This directory contains the curated comparison layer for TTSP result sets.

## Run

```sh
uv run python analysis/compare_results.py
```

The script reads `analysis/result_sets.csv`, validates stored tours against `datasets/`, and writes generated outputs to `analysis/output/`.

## Running Experiments on GitHub Actions

Use the manual `GA Experiments` workflow to run GA result sets without using local compute. The workflow accepts comma-separated instance size classes, travel budgets, and seeds, then uploads `results/` and `results_metadata/genetic/` as artifacts for each matrix job.

Use the manual `Greedy Experiments` workflow to run Greedy Baseline result sets across comma-separated instance size classes and travel budgets. It uploads `results/` and `results_metadata/greedy/` artifacts for each matrix job.

The dataset collections must be committed to Git for GitHub-hosted runners to access them.

Both workflows support batched runs with `max_instances` and `instance_offset`. Use `max_instances=0` to run all instances. To split a 100-instance collection into four batches, run the same workflow four times with `max_instances=25` and `instance_offset` values `0`, `25`, `50`, and `75`. Output directory names stay the same across batches, so downloaded artifacts can be merged into the same `results/` and `results_metadata/` folders.

After downloading and merging the artifacts into the repository root, add matching rows to `analysis/result_sets.csv` if they are new result sets, then run the comparison script again.

## Outputs

- `raw_validated_results.csv`: every included result file with validation fields.
- `per_instance_comparison.csv`: complete-case comparison rows for greedy, GA best-of-N summaries, and Jsprit Heuristic best-of-N summaries when included.
- `aggregate_summary.csv`: scenario-level aggregate comparison.
- `aggregate_summary.md`: Markdown table for quick review.
- `aggregate_summary.tex`: LaTeX table for the thesis.
- `thesis_tables.tex`: thesis-focused LaTeX tables grouped by graph family and instance size class, with `L_{\max}` rows for travel budgets.
- `plots/`: generated reward-ratio comparison plots.

The Small-Instance Exact Solver is used as an optimum reference where available. Otherwise, reward ratios use the best-known reward among comparable valid result sets. Jsprit metadata can include `explicit_reward`; validated TTSP reward remains the primary reward for ratios, winners, and aggregate summaries.
