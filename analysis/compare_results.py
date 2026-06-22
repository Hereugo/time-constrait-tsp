import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "analysis" / "result_sets.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "analysis" / "output"
AVERAGE_SUMMARY_LABELS = {
    "ga": "Genetic Algorithm Average-of-{seed_count}",
    "jsprit": "Jsprit Heuristic Average-of-{seed_count}",
}
BEST_SUMMARY_LABELS = {
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
        runtimes = group["runtime_seconds"].dropna()
        row["result_set_id"] = f"{approach_id}_best_of_{seed_count}_{row['scenario_id']}"
        row["source_result_set_id"] = selected["result_set_id"]
        row["approach_id"] = f"{approach_id}_best_of_n"
        row["approach_label"] = BEST_SUMMARY_LABELS[approach_id].format(seed_count=seed_count)
        row["seed_count"] = seed_count
        row["selected_seed_runtime_seconds"] = selected.get("runtime_seconds")
        row["runtime_seconds"] = runtimes.sum() if len(runtimes) == len(group) else None
        rows.append(row)
    return pd.DataFrame(rows)


def average_of_n_rows(raw: pd.DataFrame, approach_id: str) -> pd.DataFrame:
    candidates = raw[(raw["approach_id"] == approach_id) & (~raw["is_reference"]) & (raw["is_valid"])]
    if candidates.empty:
        return pd.DataFrame(columns=raw.columns)

    rows = []
    for (_, _, graph), group in candidates.groupby(["scenario_id", "collection", "graph"], sort=True):
        seed_count = group["seed"].nunique()
        row = group.sort_values(["result_set_id"]).iloc[0].to_dict()
        runtimes = group["runtime_seconds"].dropna()
        row["result_set_id"] = f"{approach_id}_average_of_{seed_count}_{row['scenario_id']}"
        row["source_result_set_id"] = ";".join(sorted(group["result_set_id"].astype(str)))
        row["approach_id"] = f"{approach_id}_average_of_n"
        row["approach_label"] = AVERAGE_SUMMARY_LABELS[approach_id].format(seed_count=seed_count)
        row["seed"] = None
        row["seed_count"] = seed_count
        row["reward"] = group["reward"].mean()
        row["cost"] = group["cost"].mean()
        row["runtime_seconds"] = runtimes.mean() if len(runtimes) == len(group) else None
        row["computed_reward"] = group["computed_reward"].mean()
        row["computed_cost"] = group["computed_cost"].mean()
        row["unique_visited_nodes"] = group["unique_visited_nodes"].mean()
        row["route_hops"] = group["route_hops"].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def comparable_rows(raw: pd.DataFrame) -> pd.DataFrame:
    deterministic = raw[(raw["approach_id"] == "greedy") & (~raw["is_reference"]) & (raw["is_valid"])]
    stochastic_summaries = [average_of_n_rows(raw, approach_id) for approach_id in AVERAGE_SUMMARY_LABELS]
    candidates = pd.concat([deterministic, *stochastic_summaries], ignore_index=True)

    complete_keys = []
    required = {"greedy", "ga_average_of_n"}
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
        reference_reward = float(group["reward"].max())
        if key in references.index:
            reference_rows = references.loc[[key]] if isinstance(references.loc[key], pd.Series) else references.loc[key]
            if isinstance(reference_rows, pd.Series):
                reference_reward = float(reference_rows["reward"])
            else:
                reference_reward = float(reference_rows.sort_values(["reward", "cost"], ascending=[False, True]).iloc[0]["reward"])
            reference_type = "optimum"
            for _, row in group.iterrows():
                if float(row["reward"]) > reference_reward:
                    anomalies.append((key, row["result_set_id"], float(row["reward"]), reference_reward))

        winner = best_row(group.to_dict("records"))
        for _, row in group.iterrows():
            output = row.to_dict()
            output["reference_type"] = reference_type
            output["reference_reward"] = reference_reward
            output["reward_ratio"] = reward_ratio(float(row["reward"]), reference_reward)
            output["is_winner"] = row["result_set_id"] == winner["result_set_id"]
            annotated.append(output)

    if anomalies:
        details = "\n".join(
            f"{key}: {result_set_id} reward {reward} exceeds exact reward {exact_reward}"
            for key, result_set_id, reward, exact_reward in anomalies[:20]
        )
        raise ValueError(f"Heuristic result exceeded exact reference reward.\n{details}")

    return pd.DataFrame(annotated)


def reward_ratio(reward: float, reference_reward: float) -> float | None:
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


def reliability_summary(raw: pd.DataFrame, approach_id: str = "ga") -> pd.DataFrame:
    candidates = raw[(raw["approach_id"] == approach_id) & (~raw["is_reference"]) & (raw["is_valid"])]
    if candidates.empty:
        return pd.DataFrame()

    rows = []
    group_columns = ["scenario_id", "collection", "budget", "graph"]
    for (_, collection, budget, graph), group in candidates.groupby(group_columns, sort=True):
        if group["seed"].nunique() < 2:
            continue
        reward = group["reward"]
        reward_mean = reward.mean()
        reward_std = reward.std()
        reward_range = reward.max() - reward.min()
        _, instance_size = collection_parts(collection)
        rows.append(
            {
                "collection": collection,
                "instance_size": instance_size,
                "budget": budget,
                "graph": graph,
                "seed_count": int(group["seed"].nunique()),
                "mean_reward": reward_mean,
                "reward_std": reward_std,
                "relative_reward_std": reward_std / reward_mean if reward_mean else 0,
                "reward_range": reward_range,
                "identical_seed_rewards": reward_range == 0,
            }
        )

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    summary_rows = []
    size_order = {"small": 0, "medium": 1, "large": 2}
    for (instance_size, budget), group in frame.groupby(["instance_size", "budget"], sort=False):
        summary_rows.append(
            {
                "instance_size": instance_size,
                "budget": int(budget),
                "graph_budget_cases": int(len(group)),
                "seed_count": int(group["seed_count"].max()),
                "identical_seed_cases": int(group["identical_seed_rewards"].sum()),
                "identical_seed_share": group["identical_seed_rewards"].mean(),
                "mean_reward_std": group["reward_std"].mean(),
                "mean_relative_reward_std": group["relative_reward_std"].mean(),
                "median_reward_range": group["reward_range"].median(),
                "max_reward_range": group["reward_range"].max(),
            }
        )
    return pd.DataFrame(summary_rows).sort_values(
        ["instance_size", "budget"], key=lambda column: column.map(lambda value: size_order.get(value, 99))
        if column.name == "instance_size"
        else column
    )


def reliability_markdown_table(frame: pd.DataFrame) -> str:
    table = frame.copy()
    table["identical_seed_share"] = table["identical_seed_share"].map(lambda value: f"{value:.3f}")
    table["mean_reward_std"] = table["mean_reward_std"].map(lambda value: f"{value:.3f}")
    table["mean_relative_reward_std"] = table["mean_relative_reward_std"].map(lambda value: f"{value:.4f}")
    table["median_reward_range"] = table["median_reward_range"].map(lambda value: f"{value:.1f}")
    table["max_reward_range"] = table["max_reward_range"].map(lambda value: f"{value:.1f}")
    return table.to_markdown(index=False, disable_numparse=True) + "\n"


def reliability_latex_table(frame: pd.DataFrame) -> str:
    rows = []
    for _, row in frame.iterrows():
        rows.append(
            {
                "Instance size": title_label(row["instance_size"]),
                "Travel budget": str(int(row["budget"])),
                "Graph-budget cases": str(int(row["graph_budget_cases"])),
                "Same reward cases": str(int(row["identical_seed_cases"])),
                "Same reward share": thesis_number(row["identical_seed_share"], 3),
                "Mean rel. std.": thesis_number(row["mean_relative_reward_std"], 4),
                "Median range": thesis_number(row["median_reward_range"], 1),
                "Max range": thesis_number(row["max_reward_range"], 1),
            }
        )

    row_end = " " + chr(92) * 2
    lines = ["\\begin{tabular}{lrrrrrrr}", "\\toprule"]
    lines.append(" & ".join(latex_escape(column) for column in rows[0]) + row_end)
    lines.append("\\midrule")
    for row in rows:
        lines.append(" & ".join(row.values()) + row_end)
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines) + "\n"


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


def collection_parts(collection: str) -> tuple[str, str]:
    for size in ("small", "medium", "large"):
        suffix = f"_{size}"
        if collection.endswith(suffix):
            return collection[: -len(suffix)], size
    return collection, "unknown"


def title_label(value: str) -> str:
    return value.replace("_", " ").title()


def exact_thesis_aggregate(raw: pd.DataFrame, per_instance: pd.DataFrame) -> pd.DataFrame:
    exact = raw[(raw["is_reference"]) & (raw["is_valid"])].copy()
    if exact.empty or per_instance.empty:
        return pd.DataFrame()

    complete_keys = per_instance[["scenario_id", "collection", "budget", "graph"]].drop_duplicates()
    exact = exact.merge(complete_keys, on=["scenario_id", "collection", "budget", "graph"])
    exact = exact[exact["collection"].map(lambda collection: collection_parts(collection)[1] == "small")]
    if exact.empty:
        return pd.DataFrame()

    exact["reward_ratio"] = 1.0
    exact["budget_utilization"] = exact["cost"] / exact["budget"]
    rows = []
    group_columns = ["scenario_id", "collection", "budget", "approach_id", "approach_label"]
    for key, group in exact.groupby(group_columns, sort=True):
        scenario, collection, budget, approach_id, approach_label = key
        runtime = group["runtime_seconds"].dropna()
        rows.append(
            {
                "scenario_id": scenario,
                "collection": collection,
                "budget": budget,
                "reference_type": "optimum",
                "approach_id": approach_id,
                "approach_label": approach_label,
                "compared_instances": int(group["graph"].nunique()),
                "mean_reward": group["reward"].mean(),
                "mean_reward_ratio": group["reward_ratio"].mean(),
                "mean_budget_utilization": group["budget_utilization"].mean(),
                "mean_runtime_seconds": runtime.mean() if not runtime.empty else None,
            }
        )
    return pd.DataFrame(rows)


def thesis_aggregate(raw: pd.DataFrame, per_instance: pd.DataFrame, aggregate_frame: pd.DataFrame) -> pd.DataFrame:
    base = aggregate_frame.copy()
    exact = exact_thesis_aggregate(raw, per_instance)
    if not exact.empty:
        base = pd.concat([base, exact], ignore_index=True, sort=False)

    rows = []
    for _, row in base.iterrows():
        family, size = collection_parts(row["collection"])
        output = row.to_dict()
        output["graph_family"] = family
        output["instance_size"] = size
        rows.append(output)
    return pd.DataFrame(rows)


def thesis_number(value: object, decimals: int) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.{decimals}f}"


def bold_latex(value: str) -> str:
    return f"\\textbf{{{value}}}" if value else value


def mark_best_display_values(rows: list[dict], column: str, higher_is_better: bool) -> set[int]:
    candidates = [(index, row[column]) for index, row in enumerate(rows) if row[column]]
    if not candidates:
        return set()

    ordered = sorted(candidates, key=lambda item: float(item[1]), reverse=higher_is_better)
    best_value = ordered[0][1]
    tied_indexes = {index for index, value in candidates if value == best_value}
    exact_ties = {index for index in tied_indexes if rows[index]["approach_id"] == "exact"}
    return exact_ties or tied_indexes


def thesis_table(frame: pd.DataFrame, graph_family: str, instance_size: str) -> str:
    method_order = {
        "greedy": 0,
        "ga_average_of_n": 1,
        "exact": 2,
    }
    instance_vertex_counts = {
        "small": 10,
        "medium": 100,
        "large": 1000,
    }
    row_end = " " + chr(92) * 2
    table = frame.copy()
    table["method_order"] = table["approach_id"].map(lambda value: method_order.get(value, 99))
    table = table.sort_values(["budget", "method_order", "approach_label"])

    caption = f"{title_label(graph_family)} {title_label(instance_size)} instances"
    vertex_count = instance_vertex_counts.get(instance_size)
    if vertex_count is not None:
        caption = f"{caption} ({vertex_count} vertices each)"
    lines = [
        "\\begin{table}[ht]",
        "\\centering",
        f"\\caption{{{latex_escape(caption)}. $L_{{\\max}}$ denotes the travel budget.}}",
        "\\begin{tabular}{lrrrr}",
        "\\toprule",
        "Method & Instances & Avg. reward & Avg. budget utilization & Avg. runtime (s)" + row_end,
        "\\midrule",
    ]

    for budget, budget_group in table.groupby("budget", sort=True):
        lines.append(f"\\multicolumn{{5}}{{l}}{{$L_{{\\max}}={int(budget)}$}}" + row_end)
        rows = []
        for _, row in budget_group.iterrows():
            rows.append(
                {
                    "approach_id": row["approach_id"],
                    "approach_label": latex_escape(row["approach_label"]),
                    "compared_instances": str(int(row["compared_instances"])),
                    "mean_reward": thesis_number(row["mean_reward"], 1),
                    "mean_budget_utilization": thesis_number(row["mean_budget_utilization"], 3),
                    "mean_runtime_seconds": thesis_number(row["mean_runtime_seconds"], 3),
                }
            )

        bold_indexes = {
            "mean_reward": mark_best_display_values(rows, "mean_reward", True),
            "mean_budget_utilization": mark_best_display_values(rows, "mean_budget_utilization", True),
            "mean_runtime_seconds": mark_best_display_values(rows, "mean_runtime_seconds", False),
        }
        for index, row in enumerate(rows):
            values = [
                row["approach_label"],
                row["compared_instances"],
                bold_latex(row["mean_reward"]) if index in bold_indexes["mean_reward"] else row["mean_reward"],
                bold_latex(row["mean_budget_utilization"])
                if index in bold_indexes["mean_budget_utilization"]
                else row["mean_budget_utilization"],
                bold_latex(row["mean_runtime_seconds"])
                if index in bold_indexes["mean_runtime_seconds"]
                else row["mean_runtime_seconds"],
            ]
            lines.append(" & ".join(values) + row_end)

    label = f"tab:{graph_family}-{instance_size}-ttsp-results".replace("_", "-")
    lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        f"\\label{{{label}}}",
        "\\end{table}",
    ])
    return "\n".join(lines) + "\n"


def write_thesis_tables(raw: pd.DataFrame, per_instance: pd.DataFrame, aggregate_frame: pd.DataFrame, output_dir: Path) -> None:
    thesis = thesis_aggregate(raw, per_instance, aggregate_frame)
    size_order = {"small": 0, "medium": 1, "large": 2}
    groups = sorted(
        thesis.groupby(["graph_family", "instance_size"], sort=False),
        key=lambda item: (item[0][0], size_order.get(item[0][1], 99)),
    )
    parts = []
    for (graph_family, instance_size), group in groups:
        if instance_size == "unknown":
            continue
        parts.append(thesis_table(group, graph_family, instance_size))
    (output_dir / "thesis_tables.tex").write_text("\n".join(parts), encoding="utf-8")


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


def write_reliability_outputs(frame: pd.DataFrame, output_dir: Path) -> None:
    if frame.empty:
        return
    frame.to_csv(output_dir / "ga_seed_reliability_by_size.csv", index=False)
    (output_dir / "ga_seed_reliability_by_size.md").write_text(reliability_markdown_table(frame), encoding="utf-8")
    (output_dir / "ga_seed_reliability_by_size.tex").write_text(reliability_latex_table(frame), encoding="utf-8")


def write_plots(per_instance: pd.DataFrame, aggregate_frame: pd.DataFrame, output_dir: Path) -> None:
    import numpy as np
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

    size_order = ["small", "medium", "large"]
    runtime_data = aggregate_frame.copy()
    runtime_data[["graph_family", "instance_size"]] = runtime_data["collection"].apply(
        lambda value: pd.Series(collection_parts(value))
    )
    runtime_data = runtime_data[
        (runtime_data["instance_size"].isin(size_order))
        & (runtime_data["mean_runtime_seconds"].notna())
        & (runtime_data["mean_runtime_seconds"] > 0)
    ]

    required_sizes = set(size_order)
    common_budgets = [
        budget
        for budget, group in runtime_data.groupby("budget", sort=True)
        if set(group["instance_size"]) >= required_sizes
    ]
    runtime_data = runtime_data[runtime_data["budget"].isin(common_budgets)]

    complete_approaches = []
    expected_points = len(common_budgets) * len(size_order)
    for approach_label, group in runtime_data.groupby("approach_label", sort=True):
        actual_points = group[["budget", "instance_size"]].drop_duplicates().shape[0]
        if actual_points == expected_points:
            complete_approaches.append(approach_label)

    if common_budgets and complete_approaches:
        x_positions = np.arange(len(size_order))
        fig, axes = plt.subplots(
            1,
            len(complete_approaches),
            figsize=(5 * len(complete_approaches), 4.5),
            sharey=True,
        )
        axes = np.atleast_1d(axes)

        for axis, approach_label in zip(axes, complete_approaches):
            approach_data = runtime_data[runtime_data["approach_label"] == approach_label]
            for budget in common_budgets:
                budget_data = approach_data[approach_data["budget"] == budget]
                runtimes = np.array(
                    [
                        budget_data[budget_data["instance_size"] == size]["mean_runtime_seconds"].iloc[0]
                        for size in size_order
                    ],
                    dtype=float,
                )
                axis.plot(x_positions, runtimes, marker="o", label=f"Budget {int(budget)}")

            axis.set_title(approach_label)
            axis.set_xticks(x_positions, [title_label(size) for size in size_order])
            axis.set_xlabel("Instance size class")
            axis.set_yscale("log")
            axis.grid(True, axis="y", which="both", alpha=0.3)

        axes[0].set_ylabel("Mean per-instance runtime (s)")
        fig.suptitle("Mean per-instance runtime by instance size")
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, title="Travel budget", loc="lower center", ncol=len(common_budgets))
        fig.tight_layout(rect=(0, 0.1, 1, 0.95))
        plt.savefig(plot_dir / "mean_runtime_by_instance_size.png", dpi=200)
        plt.close(fig)


def write_outputs(
    raw: pd.DataFrame,
    per_instance: pd.DataFrame,
    aggregate_frame: pd.DataFrame,
    reliability_frame: pd.DataFrame,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw.to_csv(output_dir / "raw_validated_results.csv", index=False)
    per_instance.to_csv(output_dir / "per_instance_comparison.csv", index=False)
    aggregate_frame.to_csv(output_dir / "aggregate_summary.csv", index=False)
    write_tables(aggregate_frame, output_dir)
    write_reliability_outputs(reliability_frame, output_dir)
    write_thesis_tables(raw, per_instance, aggregate_frame, output_dir)
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
    reliability_frame = reliability_summary(raw)
    write_outputs(raw, per_instance, aggregate_frame, reliability_frame, args.output_dir)
    print(f"Wrote comparison outputs to {args.output_dir.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
