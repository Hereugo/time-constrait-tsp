import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "analysis" / "result_sets.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "analysis" / "output"
STOCHASTIC_SUMMARY_LABELS = {
    "ga": "Genetic Algorithm Best-of-{seed_count}",
    "jsprit": "Jsprit Heuristic Best-of-{seed_count}",
}


@dataclass(frozen=True)
class Instance:
    n: int
    rewards: list[int]
    edges: dict[tuple[int, int], int]


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def parse_optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def parse_optional_float(value: str) -> float | None:
    value = value.strip()
    return float(value) if value else None


def scenario_id(collection: str, budget: int) -> str:
    return f"{collection}_budget{budget:03d}"


def read_manifest(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = []
        for row in csv.DictReader(handle):
            if not parse_bool(row["include_in_main"]):
                continue
            row["budget"] = int(row["budget"])
            row["seed"] = parse_optional_int(row["seed"])
            row["generations"] = parse_optional_int(row["generations"])
            row["population_size"] = parse_optional_int(row["population_size"])
            row["mutation_rate"] = parse_optional_float(row["mutation_rate"])
            row["is_reference"] = parse_bool(row["is_reference"])
            row["scenario_id"] = scenario_id(row["collection"], row["budget"])
            rows.append(row)
    return rows


def read_instance(path: Path) -> Instance:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError(f"Dataset file {path} must contain at least two lines.")

    n, m = map(int, lines[0].split())
    rewards = list(map(int, lines[1].split()))
    if len(rewards) != n:
        raise ValueError(f"Dataset file {path} declares {n} nodes but has {len(rewards)} rewards.")

    edge_lines = lines[2:]
    if len(edge_lines) != m:
        raise ValueError(f"Dataset file {path} declares {m} edges but has {len(edge_lines)} edge rows.")

    edges = {}
    for line in edge_lines:
        u, v, weight = map(int, line.split())
        edges[(u, v)] = weight
        edges[(v, u)] = weight
    return Instance(n=n, rewards=rewards, edges=edges)


def read_solution(path: Path) -> tuple[int, int, list[int]]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 2:
        raise ValueError(f"Solution file {path} must contain exactly two non-empty lines.")
    reward, cost = map(int, lines[0].split())
    route = list(map(int, lines[1].split()))
    return reward, cost, route


def validate_solution(instance: Instance, declared_reward: int, declared_cost: int, route: list[int], depot: int = 1) -> dict:
    notes = []
    invalid_nodes = [node for node in route if node < 1 or node > instance.n]
    starts_at_depot = bool(route) and route[0] == depot
    ends_at_depot = bool(route) and route[-1] == depot

    if not starts_at_depot:
        notes.append("route_does_not_start_at_depot")
    if not ends_at_depot:
        notes.append("route_does_not_end_at_depot")
    if invalid_nodes:
        notes.append("invalid_nodes")

    computed_cost = 0
    invalid_edges = []
    for left, right in zip(route, route[1:]):
        weight = instance.edges.get((left, right))
        if weight is None:
            invalid_edges.append(f"{left}-{right}")
        else:
            computed_cost += weight
    if invalid_edges:
        notes.append("invalid_edges")

    visited = {node for node in route if 1 <= node <= instance.n}
    visited.discard(depot)
    computed_reward = sum(instance.rewards[node - 1] for node in visited)

    cost_matches = not invalid_edges and computed_cost == declared_cost
    reward_matches = computed_reward == declared_reward
    if not cost_matches:
        notes.append("cost_mismatch")
    if not reward_matches:
        notes.append("reward_mismatch")

    is_valid = starts_at_depot and ends_at_depot and not invalid_nodes and not invalid_edges and cost_matches and reward_matches
    return {
        "is_valid": is_valid,
        "validation_notes": ";".join(notes),
        "computed_reward": computed_reward,
        "computed_cost": computed_cost if not invalid_edges else None,
        "unique_visited_nodes": len(visited),
        "route_hops": max(len(route) - 1, 0),
    }


def load_metadata(manifest_row: dict, graph_name: str, results_metadata_root: Path) -> dict:
    metadata_dir = manifest_row["metadata_dir"].strip()
    if not metadata_dir:
        return {}

    metadata_path = results_metadata_root / metadata_dir / f"{Path(graph_name).stem}.json"
    if not metadata_path.exists():
        return {"metadata_missing": True}
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def raw_rows(manifest_rows: list[dict], datasets_root: Path, results_root: Path, results_metadata_root: Path) -> list[dict]:
    rows = []
    instance_cache: dict[Path, Instance] = {}

    for result_set in manifest_rows:
        dataset_dir = datasets_root / result_set["collection"]
        result_dir = results_root / result_set["result_dir"]
        if not dataset_dir.exists():
            raise ValueError(f"Dataset collection does not exist: {dataset_dir}")
        if not result_dir.exists():
            raise ValueError(f"Result directory does not exist: {result_dir}")

        for dataset_path in sorted(path for path in dataset_dir.iterdir() if path.is_file() and not path.name.startswith(".")):
            solution_path = result_dir / dataset_path.name
            if not solution_path.exists():
                continue

            if dataset_path not in instance_cache:
                instance_cache[dataset_path] = read_instance(dataset_path)
            instance = instance_cache[dataset_path]

            declared_reward, declared_cost, route = read_solution(solution_path)
            validation = validate_solution(instance, declared_reward, declared_cost, route)
            metadata = load_metadata(result_set, dataset_path.name, results_metadata_root)
            runtime_seconds = metadata.get("runtime_seconds")
            explicit_reward = metadata.get("explicit_reward")
            validated_reward = metadata.get("validated_reward")

            rows.append(
                {
                    "scenario_id": result_set["scenario_id"],
                    "collection": result_set["collection"],
                    "budget": result_set["budget"],
                    "graph": dataset_path.name,
                    "result_set_id": result_set["result_set_id"],
                    "source_result_set_id": result_set["result_set_id"],
                    "approach_id": result_set["approach_id"],
                    "approach_label": result_set["approach_label"],
                    "is_reference": result_set["is_reference"],
                    "seed": result_set["seed"],
                    "seed_count": 1 if result_set["seed"] is not None else None,
                    "generations": result_set["generations"],
                    "population_size": result_set["population_size"],
                    "mutation_rate": result_set["mutation_rate"],
                    "reward": declared_reward,
                    "cost": declared_cost,
                    "explicit_reward": explicit_reward,
                    "validated_reward": validated_reward,
                    "runtime_seconds": runtime_seconds,
                    **validation,
                }
            )
    return rows


def best_row(rows: list[dict]) -> dict:
    return sorted(
        rows,
        key=lambda row: (
            row["reward"],
            -row["cost"],
            -row["route_hops"],
            row["result_set_id"],
        ),
        reverse=True,
    )[0]


def best_of_n_rows(raw: pd.DataFrame, approach_id: str) -> pd.DataFrame:
    candidates = raw[(raw["approach_id"] == approach_id) & (~raw["is_reference"]) & (raw["is_valid"])]
    if candidates.empty:
        return pd.DataFrame(columns=raw.columns)

    rows = []
    for (_, _, graph), group in candidates.groupby(["scenario_id", "collection", "graph"], sort=True):
        selected = best_row(group.to_dict("records"))
        seed_count = group["seed"].nunique()
        row = dict(selected)
        row["result_set_id"] = f"{approach_id}_best_of_{seed_count}_{row['scenario_id']}"
        row["source_result_set_id"] = selected["result_set_id"]
        row["approach_id"] = f"{approach_id}_best_of_n"
        row["approach_label"] = STOCHASTIC_SUMMARY_LABELS[approach_id].format(seed_count=seed_count)
        row["seed_count"] = seed_count
        rows.append(row)
    return pd.DataFrame(rows)


def comparable_rows(raw: pd.DataFrame) -> pd.DataFrame:
    deterministic = raw[(raw["approach_id"] == "greedy") & (~raw["is_reference"]) & (raw["is_valid"])]
    stochastic_summaries = [best_of_n_rows(raw, approach_id) for approach_id in STOCHASTIC_SUMMARY_LABELS]
    candidates = pd.concat([deterministic, *stochastic_summaries], ignore_index=True)

    complete_keys = []
    required = {"greedy", "ga_best_of_n"}
    for key, group in candidates.groupby(["scenario_id", "collection", "budget", "graph"], sort=True):
        if set(group["approach_id"]) >= required:
            complete_keys.append(key)

    if not complete_keys:
        return pd.DataFrame(columns=list(raw.columns) + ["reference_type", "reference_reward", "reward_ratio", "is_winner"])

    complete_index = pd.MultiIndex.from_tuples(complete_keys, names=["scenario_id", "collection", "budget", "graph"])
    candidates = candidates.set_index(["scenario_id", "collection", "budget", "graph"])
    candidates = candidates.loc[candidates.index.intersection(complete_index)].reset_index()

    references = raw[(raw["is_reference"]) & (raw["is_valid"])].set_index(["scenario_id", "collection", "budget", "graph"])
    annotated = []
    anomalies = []

    for key, group in candidates.groupby(["scenario_id", "collection", "budget", "graph"], sort=True):
        reference_type = "best_known"
        reference_reward = int(group["reward"].max())
        if key in references.index:
            reference_rows = references.loc[[key]] if isinstance(references.loc[key], pd.Series) else references.loc[key]
            if isinstance(reference_rows, pd.Series):
                reference_reward = int(reference_rows["reward"])
            else:
                reference_reward = int(reference_rows.sort_values(["reward", "cost"], ascending=[False, True]).iloc[0]["reward"])
            reference_type = "optimum"
            for _, row in group.iterrows():
                if int(row["reward"]) > reference_reward:
                    anomalies.append((key, row["result_set_id"], int(row["reward"]), reference_reward))

        winner = best_row(group.to_dict("records"))
        for _, row in group.iterrows():
            output = row.to_dict()
            output["reference_type"] = reference_type
            output["reference_reward"] = reference_reward
            output["reward_ratio"] = reward_ratio(int(row["reward"]), reference_reward)
            output["is_winner"] = row["result_set_id"] == winner["result_set_id"]
            annotated.append(output)

    if anomalies:
        details = "\n".join(
            f"{key}: {result_set_id} reward {reward} exceeds exact reward {exact_reward}"
            for key, result_set_id, reward, exact_reward in anomalies[:20]
        )
        raise ValueError(f"Heuristic result exceeded exact reference reward.\n{details}")

    return pd.DataFrame(annotated)


def reward_ratio(reward: int, reference_reward: int) -> float | None:
    if reference_reward == 0:
        return 1.0 if reward == 0 else None
    return reward / reference_reward


def aggregate(per_instance: pd.DataFrame) -> pd.DataFrame:
    if per_instance.empty:
        return pd.DataFrame()

    rows = []
    group_columns = ["scenario_id", "collection", "budget", "reference_type", "approach_id", "approach_label"]
    for key, group in per_instance.groupby(group_columns, sort=True):
        scenario, collection, budget, reference_type, approach_id, approach_label = key
        runtime = group["runtime_seconds"].dropna()
        explicit_reward = group["explicit_reward"].dropna() if "explicit_reward" in group else pd.Series(dtype=float)
        rows.append(
            {
                "scenario_id": scenario,
                "collection": collection,
                "budget": budget,
                "reference_type": reference_type,
                "approach_id": approach_id,
                "approach_label": approach_label,
                "compared_instances": int(group["graph"].nunique()),
                "mean_reward": group["reward"].mean(),
                "mean_explicit_reward": explicit_reward.mean() if not explicit_reward.empty else None,
                "mean_reward_ratio": group["reward_ratio"].mean(),
                "median_reward_ratio": group["reward_ratio"].median(),
                "win_count": int(group["is_winner"].sum()),
                "mean_cost": group["cost"].mean(),
                "mean_budget_utilization": (group["cost"] / group["budget"]).mean(),
                "mean_runtime_seconds": runtime.mean() if not runtime.empty else None,
            }
        )
    return pd.DataFrame(rows).sort_values(["collection", "budget", "approach_id"])


def markdown_table(frame: pd.DataFrame) -> str:
    table = frame.copy()
    for column in ["mean_reward", "mean_explicit_reward", "mean_cost"]:
        if column in table:
            table[column] = table[column].map(lambda value: "" if pd.isna(value) else f"{value:.1f}")
    for column in ["mean_reward_ratio", "median_reward_ratio", "mean_budget_utilization"]:
        if column in table:
            table[column] = table[column].map(lambda value: f"{value:.3f}")
    if "mean_runtime_seconds" in table:
        table["mean_runtime_seconds"] = table["mean_runtime_seconds"].map(
            lambda value: "" if pd.isna(value) else f"{value:.3f}"
        )
    return table.to_markdown(index=False) + "\n"


def latex_table(frame: pd.DataFrame) -> str:
    table = frame.copy()
    rename = {
        "scenario_id": "Scenario",
        "approach_label": "Approach",
        "compared_instances": "Instances",
        "mean_reward": "Mean reward",
        "mean_explicit_reward": "Mean explicit reward",
        "mean_reward_ratio": "Mean ratio",
        "median_reward_ratio": "Median ratio",
        "win_count": "Wins",
        "mean_cost": "Mean cost",
        "mean_budget_utilization": "Budget use",
        "mean_runtime_seconds": "Runtime (s)",
    }
    columns = list(rename)
    table = table[columns].rename(columns=rename)
    align = "l" * len(table.columns)
    lines = [f"\\begin{{tabular}}{{{align}}}", "\\toprule"]
    row_end = " " + "\\\\"
    lines.append(" & ".join(latex_escape(column) for column in table.columns) + row_end)
    lines.append("\\midrule")
    for _, row in table.iterrows():
        values = [latex_value(row[column]) for column in table.columns]
        lines.append(" & ".join(values) + row_end)
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines) + "\n"


def latex_escape(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def latex_value(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return latex_escape(value)


def write_tables(aggregate_frame: pd.DataFrame, output_dir: Path) -> None:
    columns = [
        "scenario_id",
        "approach_label",
        "compared_instances",
        "mean_reward",
        "mean_explicit_reward",
        "mean_reward_ratio",
        "median_reward_ratio",
        "win_count",
        "mean_cost",
        "mean_budget_utilization",
        "mean_runtime_seconds",
    ]
    table_frame = aggregate_frame[columns]
    (output_dir / "aggregate_summary.md").write_text(markdown_table(table_frame), encoding="utf-8")
    (output_dir / "aggregate_summary.tex").write_text(latex_table(aggregate_frame), encoding="utf-8")


def write_plots(per_instance: pd.DataFrame, aggregate_frame: pd.DataFrame, output_dir: Path) -> None:
    import matplotlib.pyplot as plt

    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    bar_data = aggregate_frame.pivot(index="scenario_id", columns="approach_label", values="mean_reward_ratio")
    axis = bar_data.plot(kind="bar", figsize=(10, 5), ylim=(0, 1.05))
    axis.set_ylabel("Mean reward ratio")
    axis.set_xlabel("Scenario")
    axis.set_title("Mean reward ratio by scenario and approach")
    axis.legend(title="Approach")
    plt.tight_layout()
    plt.savefig(plot_dir / "mean_reward_ratio_by_scenario.png", dpi=200)
    plt.close()

    box_data = [
        group["reward_ratio"].dropna().to_numpy()
        for _, group in per_instance.groupby("approach_label", sort=True)
    ]
    labels = [label for label, _ in per_instance.groupby("approach_label", sort=True)]
    fig, axis = plt.subplots(figsize=(8, 5))
    axis.boxplot(box_data, tick_labels=labels)
    axis.set_ylabel("Reward ratio")
    axis.set_title("Per-instance reward-ratio distribution")
    axis.set_ylim(0, 1.05)
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    plt.savefig(plot_dir / "reward_ratio_distribution.png", dpi=200)
    plt.close(fig)


def write_outputs(raw: pd.DataFrame, per_instance: pd.DataFrame, aggregate_frame: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_validated_results.csv", index=False)
    per_instance.to_csv(output_dir / "per_instance_comparison.csv", index=False)
    aggregate_frame.to_csv(output_dir / "aggregate_summary.csv", index=False)
    write_tables(aggregate_frame, output_dir)
    write_plots(per_instance, aggregate_frame, output_dir)


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and compare TTSP result sets.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--datasets-root", type=Path, default=REPO_ROOT / "datasets")
    parser.add_argument("--results-root", type=Path, default=REPO_ROOT / "results")
    parser.add_argument("--results-metadata-root", type=Path, default=REPO_ROOT / "results_metadata")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    args = argument_parser().parse_args()
    manifest_rows = read_manifest(args.manifest)
    raw = pd.DataFrame(raw_rows(manifest_rows, args.datasets_root, args.results_root, args.results_metadata_root))
    if raw.empty:
        raise SystemExit("No result rows found from manifest.")
    per_instance = comparable_rows(raw)
    if per_instance.empty:
        raise SystemExit("No complete comparable instances found.")
    aggregate_frame = aggregate(per_instance)
    write_outputs(raw, per_instance, aggregate_frame, args.output_dir)
    print(f"Wrote comparison outputs to {args.output_dir.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
