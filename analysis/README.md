# Result Comparison

This directory contains the curated comparison layer for TTSP result sets.

## Run

```sh
uv run python analysis/compare_results.py
```

The script reads `analysis/result_sets.csv`, validates stored tours against `datasets/`, and writes generated outputs to `analysis/output/`.

## Outputs

- `raw_validated_results.csv`: every included result file with validation fields.
- `per_instance_comparison.csv`: complete-case comparison rows for greedy and GA best-of-N summaries.
- `aggregate_summary.csv`: scenario-level aggregate comparison.
- `aggregate_summary.md`: Markdown table for quick review.
- `aggregate_summary.tex`: LaTeX table for the thesis.
- `plots/`: generated reward-ratio comparison plots.

The Small-Instance Exact Solver is used as an optimum reference where available. Otherwise, reward ratios use the best-known reward among comparable valid result sets.
