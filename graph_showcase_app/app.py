from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path

import networkx as nx
import pandas as pd
from pyvis.network import Network
import streamlit as st
import streamlit.components.v1 as components

from graph_data import (
    GraphInstance,
    SolutionInstance,
    datasets_root,
    list_dataset_collections,
    list_result_directories_for_collection,
    load_graph_instance,
    load_solution_for_graph,
    result_path_for_graph,
    results_root,
)


st.set_page_config(
    page_title="Time-Constrained TSP Graph Showcase",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def collection_index() -> dict[str, list[str]]:
    return {
        collection: [str(path) for path in paths]
        for collection, paths in list_dataset_collections().items()
    }


@st.cache_data(show_spinner=False)
def load_instance(path_str: str) -> GraphInstance:
    return load_graph_instance(Path(path_str))


@st.cache_data(show_spinner=False)
def result_directory_options_for_collection(collection_name: str) -> list[str]:
    return list(list_result_directories_for_collection(collection_name))


@st.cache_data(show_spinner=False)
def load_matching_solution(
    path_str: str,
    result_directory_name: str | None,
) -> SolutionInstance | None:
    return load_solution_for_graph(Path(path_str), result_directory_name)


def build_graph(instance: GraphInstance) -> nx.Graph:
    graph = nx.Graph()

    for node, reward in instance.reward_by_node.items():
        graph.add_node(node, reward=reward)

    for edge in instance.edges:
        graph.add_edge(edge.source, edge.target, weight=edge.weight)

    return graph


def scale_values(values: list[int], low: float, high: float) -> list[float]:
    if not values:
        return []

    minimum = min(values)
    maximum = max(values)

    if minimum == maximum:
        return [low + ((high - low) / 2.0) for _ in values]

    spread = maximum - minimum
    return [low + ((value - minimum) / spread) * (high - low) for value in values]


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))


def interpolate_color(
    value: int,
    minimum: int,
    maximum: int,
    start: str = "#fde68a",
    end: str = "#dc2626",
) -> str:
    if minimum == maximum:
        ratio = 0.5
    else:
        ratio = (value - minimum) / (maximum - minimum)

    start_rgb = hex_to_rgb(start)
    end_rgb = hex_to_rgb(end)
    mixed = tuple(
        round(start_channel + ((end_channel - start_channel) * ratio))
        for start_channel, end_channel in zip(start_rgb, end_rgb)
    )
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def normalize_edge(source: int, target: int) -> tuple[int, int]:
    return (source, target) if source <= target else (target, source)


@dataclass(frozen=True)
class SolutionAnalysis:
    computed_reward: int
    computed_cost: int | None
    invalid_nodes: tuple[int, ...]
    invalid_edges: tuple[tuple[int, int], ...]
    starts_at_depot: bool
    ends_at_depot: bool
    visited_nodes: tuple[int, ...]
    visit_order_by_node: dict[int, int]
    edge_steps_by_key: dict[tuple[int, int], tuple[int, ...]]
    edge_visit_counts: dict[tuple[int, int], int]
    repeated_non_depot_nodes: tuple[int, ...]
    reward_matches: bool
    cost_matches: bool


def analyze_solution(
    instance: GraphInstance,
    graph: nx.Graph,
    solution: SolutionInstance,
    depot: int = 1,
) -> SolutionAnalysis:
    invalid_nodes = tuple(node for node in solution.route if node not in graph.nodes)

    route_body = solution.route
    if len(route_body) > 1 and route_body[0] == route_body[-1]:
        route_body = route_body[:-1]

    visited_nodes = solution.unique_route_nodes
    visit_order_by_node = {
        node: order for order, node in enumerate(visited_nodes, start=1)
    }

    repeated_counter = Counter(node for node in route_body if node != depot)
    repeated_non_depot_nodes = tuple(
        sorted(node for node, count in repeated_counter.items() if count > 1)
    )

    edge_steps: dict[tuple[int, int], list[int]] = {}
    edge_visit_counts: Counter[tuple[int, int]] = Counter()
    invalid_edges: list[tuple[int, int]] = []
    computed_cost = 0

    for step_index, (source, target) in enumerate(solution.route_edges, start=1):
        if not graph.has_edge(source, target):
            invalid_edges.append((source, target))
            continue

        edge_key = normalize_edge(source, target)
        edge_steps.setdefault(edge_key, []).append(step_index)
        edge_visit_counts[edge_key] += 1
        computed_cost += int(graph.edges[source, target]["weight"])

    computed_reward = sum(
        instance.reward_by_node.get(node, 0)
        for node in visited_nodes
        if node != depot
    )

    route_cost = computed_cost if not invalid_edges else None
    starts_at_depot = bool(solution.route) and solution.route[0] == depot
    ends_at_depot = bool(solution.route) and solution.route[-1] == depot
    reward_matches = computed_reward == solution.total_reward and not invalid_nodes
    cost_matches = route_cost == solution.total_cost and not invalid_edges

    return SolutionAnalysis(
        computed_reward=computed_reward,
        computed_cost=route_cost,
        invalid_nodes=invalid_nodes,
        invalid_edges=tuple(invalid_edges),
        starts_at_depot=starts_at_depot,
        ends_at_depot=ends_at_depot,
        visited_nodes=visited_nodes,
        visit_order_by_node=visit_order_by_node,
        edge_steps_by_key={
            edge_key: tuple(steps) for edge_key, steps in edge_steps.items()
        },
        edge_visit_counts=dict(edge_visit_counts),
        repeated_non_depot_nodes=repeated_non_depot_nodes,
        reward_matches=reward_matches,
        cost_matches=cost_matches,
    )


def build_solution_step_frame(
    graph: nx.Graph,
    solution: SolutionInstance,
) -> pd.DataFrame:
    rows = []
    for step_index, (source, target) in enumerate(solution.route_edges, start=1):
        weight = graph.edges[source, target]["weight"] if graph.has_edge(source, target) else None
        rows.append(
            {
                "Step": step_index,
                "From": source,
                "To": target,
                "Weight": weight,
                "Valid edge": weight is not None,
            }
        )
    return pd.DataFrame(rows)


def render_interactive_graph(
    instance: GraphInstance,
    show_edge_weights: bool,
    show_reward_labels: bool,
    physics_solver: str,
    repulsion_strength: int,
    spring_length: int,
    spring_stiffness: float,
    damping: float,
    node_spacing: int,
    show_solution_overlay: bool,
    solution: SolutionInstance | None,
    solution_analysis: SolutionAnalysis | None,
) -> tuple[str, nx.Graph]:
    graph = build_graph(instance)
    rewards = [graph.nodes[node]["reward"] for node in graph.nodes]
    weights = [graph.edges[edge]["weight"] for edge in graph.edges]

    reward_min = min(rewards) if rewards else 0
    reward_max = max(rewards) if rewards else 1

    node_sizes = scale_values(rewards, 18, 42)
    edge_widths = scale_values(weights, 1.5, 5.0)
    node_size_map = {node: size for node, size in zip(graph.nodes, node_sizes)}
    edge_width_map = {
        normalize_edge(source, target): width
        for (source, target), width in zip(graph.edges, edge_widths)
    }

    visited_nodes = set()
    visit_order_by_node: dict[int, int] = {}
    edge_steps_by_key: dict[tuple[int, int], tuple[int, ...]] = {}
    edge_visit_counts: dict[tuple[int, int], int] = {}
    if show_solution_overlay and solution is not None and solution_analysis is not None:
        visited_nodes = set(solution_analysis.visited_nodes)
        visit_order_by_node = solution_analysis.visit_order_by_node
        edge_steps_by_key = solution_analysis.edge_steps_by_key
        edge_visit_counts = solution_analysis.edge_visit_counts

    network = Network(
        height="760px",
        width="100%",
        bgcolor="#f8fafc",
        font_color="#0f172a",
        notebook=False,
        directed=False,
        cdn_resources="in_line",
    )

    for node in graph.nodes:
        reward = graph.nodes[node]["reward"]
        degree = graph.degree(node)
        is_solution_node = node in visited_nodes
        visit_order = visit_order_by_node.get(node)

        label = str(node)
        if show_reward_labels:
            label = f"{node}\nR={reward}"
        if is_solution_node and visit_order is not None:
            label = f"{label}\nS{visit_order}"

        border_color = "#d97706" if node == 1 else "#2563eb" if is_solution_node else "#0f172a"
        highlight_border = "#b45309" if node == 1 else "#1d4ed8" if is_solution_node else "#1e293b"
        fill_color = interpolate_color(reward, reward_min, reward_max)

        title_parts = [
            f"<strong>Node {node}</strong>",
            f"Reward: {reward}",
            f"Degree: {degree}",
        ]
        if node == 1:
            title_parts.append("Start / end node")
        if is_solution_node and visit_order is not None:
            title_parts.append(
                f"Visited in solution: position {visit_order} of {len(visited_nodes)}"
            )

        network.add_node(
            node,
            label=label,
            title="<br>".join(title_parts),
            size=node_size_map[node] + (5 if is_solution_node else 0),
            borderWidth=4.5 if node == 1 else 3.0 if is_solution_node else 1.5,
            color={
                "background": fill_color,
                "border": border_color,
                "highlight": {"background": fill_color, "border": highlight_border},
                "hover": {"background": fill_color, "border": highlight_border},
            },
        )

    for source, target in graph.edges:
        weight = graph.edges[source, target]["weight"]
        edge_key = normalize_edge(source, target)
        step_numbers = edge_steps_by_key.get(edge_key, ())
        step_text = ", ".join(str(step) for step in step_numbers)
        is_solution_edge = bool(step_numbers)
        edge_uses = edge_visit_counts.get(edge_key, 0)

        title_parts = [
            f"Edge {source} - {target}",
            f"Weight: {weight}",
        ]
        if is_solution_edge:
            title_parts.append(f"Solution step(s): {step_text}")
            if edge_uses > 1:
                title_parts.append(f"Used {edge_uses} times in the stored route")

        network.add_edge(
            source,
            target,
            label=str(weight) if show_edge_weights else "",
            title="<br>".join(title_parts),
            width=edge_width_map[edge_key] + (4.5 if is_solution_edge else 0),
            color={
                "color": "#dc2626" if is_solution_edge else "rgba(100, 116, 139, 0.40)",
                "highlight": "#991b1b" if is_solution_edge else "#0f172a",
                "hover": "#991b1b" if is_solution_edge else "#0f172a",
            },
            dashes=not is_solution_edge,
        )

    physics_options = {
        "interaction": {
            "dragNodes": True,
            "dragView": True,
            "hover": True,
            "keyboard": True,
            "multiselect": True,
            "navigationButtons": True,
            "tooltipDelay": 100,
            "zoomView": True,
        },
        "layout": {"improvedLayout": True},
        "nodes": {
            "font": {"face": "Arial", "size": 15, "multi": True},
            "shadow": {"enabled": True, "color": "rgba(15, 23, 42, 0.12)", "size": 10},
        },
        "edges": {
            "font": {
                "align": "top",
                "size": 14,
                "strokeWidth": 6,
                "strokeColor": "#f8fafc",
            },
            "shadow": {"enabled": False},
            "smooth": False,
        },
        "physics": {
            "enabled": True,
            "solver": physics_solver,
            "stabilization": {
                "enabled": True,
                "fit": True,
                "iterations": 500,
                "updateInterval": 25,
            },
            "minVelocity": 0.2,
            "timestep": 0.35,
            "barnesHut": {
                "avoidOverlap": 0.3,
                "centralGravity": 0.15,
                "damping": damping,
                "gravitationalConstant": -repulsion_strength,
                "springConstant": spring_stiffness,
                "springLength": spring_length,
            },
            "forceAtlas2Based": {
                "avoidOverlap": 0.3,
                "centralGravity": 0.04,
                "damping": damping,
                "gravitationalConstant": -repulsion_strength,
                "springConstant": spring_stiffness,
                "springLength": spring_length,
            },
            "repulsion": {
                "centralGravity": 0.18,
                "damping": damping,
                "nodeDistance": node_spacing,
                "springConstant": spring_stiffness,
                "springLength": spring_length,
            },
        },
    }
    network.set_options(json.dumps(physics_options))
    return network.generate_html(), graph


def collection_summary_frame(collections: dict[str, list[str]]) -> pd.DataFrame:
    rows = []
    for name, paths in collections.items():
        sample = load_instance(paths[0])
        rows.append(
            {
                "Collection": name,
                "Graphs": len(paths),
                "Sample nodes": sample.node_count,
                "Sample edges": sample.edge_count,
            }
        )
    return pd.DataFrame(rows)


def result_directory_summary_frame(
    collection_name: str,
    graph_name: str,
    selected_result_directory_name: str | None,
) -> pd.DataFrame:
    rows = []
    for directory_name, result_files in list_result_directories_for_collection(collection_name).items():
        rows.append(
            {
                "Result directory": directory_name,
                "Graphs": len(result_files),
                "Has current graph": (results_root() / directory_name / graph_name).exists(),
                "Selected": directory_name == selected_result_directory_name,
            }
        )
    return pd.DataFrame(rows)


def result_comparison_frame(
    instance: GraphInstance,
    graph: nx.Graph,
    graph_path: str,
    selected_result_directory_name: str | None,
) -> pd.DataFrame:
    rows = []
    for directory_name in result_directory_options_for_collection(instance.collection):
        solution = load_matching_solution(graph_path, directory_name)
        if solution is None:
            continue

        analysis = analyze_solution(instance, graph, solution)
        valid = (
            analysis.starts_at_depot
            and analysis.ends_at_depot
            and not analysis.invalid_nodes
            and not analysis.invalid_edges
            and analysis.reward_matches
            and analysis.cost_matches
        )
        rows.append(
            {
                "Result directory": directory_name,
                "Reward": solution.total_reward,
                "Cost": solution.total_cost,
                "Unique visited nodes": len(analysis.visited_nodes),
                "Route hops": max(len(solution.route) - 1, 0),
                "Valid": valid,
                "Selected": directory_name == selected_result_directory_name,
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(
        ["Reward", "Cost", "Route hops", "Result directory"],
        ascending=[False, True, True, True],
    )


collections = collection_index()
no_result_directory_label = "No result directory"

st.title("Time-Constrained TSP Graph Showcase")
st.caption(
    "Browse the dataset instances in `datasets/`, inspect weighted edges, and compare the overlay from whichever result directory you choose under `results/`."
)

if not collections:
    st.error(f"No dataset collections were found under `{datasets_root()}`.")
    st.stop()

solver_labels = {
    "forceAtlas2Based": "ForceAtlas2 style",
    "barnesHut": "Barnes-Hut",
    "repulsion": "Repulsion",
}

with st.sidebar:
    st.header("Controls")
    if st.button("Refresh datasets/results"):
        st.cache_data.clear()
        st.rerun()
    collection_name = st.selectbox("Dataset collection", list(collections))
    graph_path = st.selectbox(
        "Graph instance",
        collections[collection_name],
        format_func=lambda path_str: Path(path_str).name,
    )
    available_result_directories = result_directory_options_for_collection(collection_name)
    result_directory_options = [no_result_directory_label, *available_result_directories]
    selected_result_directory_option = st.selectbox(
        "Result directory",
        result_directory_options,
        index=1 if available_result_directories else 0,
        help="Each top-level directory under `results/` can represent a different parameter setting or solver run.",
    )
    selected_result_directory_name = (
        None
        if selected_result_directory_option == no_result_directory_label
        else selected_result_directory_option
    )
    solution = load_matching_solution(graph_path, selected_result_directory_name)
    show_solution_overlay = st.toggle(
        "Show solution overlay",
        value=selected_result_directory_name is not None and solution is not None,
        disabled=selected_result_directory_name is None or solution is None,
        help="Highlights the stored tour from the selected result directory.",
    )
    physics_solver = st.selectbox(
        "Physics solver",
        list(solver_labels),
        format_func=lambda solver: solver_labels[solver],
        help="All of these keep the graph interactive, but they spread the nodes differently.",
    )
    repulsion_strength = st.slider(
        "Repulsion strength",
        min_value=300,
        max_value=6000,
        value=1600,
        step=100,
        help="Higher values push nodes farther apart.",
    )
    spring_length = st.slider(
        "Spring length",
        min_value=40,
        max_value=260,
        value=120,
        step=10,
        help="Preferred resting length of the edge springs.",
    )
    spring_stiffness = st.slider(
        "Spring stiffness",
        min_value=0.001,
        max_value=0.12,
        value=0.04,
        step=0.001,
        format="%.3f",
        help="Higher values make edges pull harder.",
    )
    damping = st.slider(
        "Damping",
        min_value=0.05,
        max_value=0.9,
        value=0.35,
        step=0.05,
        help="Higher values calm the motion faster.",
    )
    node_spacing = st.slider(
        "Node spacing",
        min_value=80,
        max_value=400,
        value=180,
        step=10,
        help="Used most strongly by the repulsion solver.",
    )
    show_edge_weights = st.toggle("Show edge weights", value=True)
    show_reward_labels = st.toggle("Show reward labels", value=True)
    st.markdown("---")
    st.write("Current dataset file")
    st.code(Path(graph_path).relative_to(datasets_root().parent).as_posix(), language="text")
    st.write("Selected result directory")
    if selected_result_directory_name is None:
        st.code(no_result_directory_label, language="text")
    else:
        st.code(selected_result_directory_name, language="text")
    st.write("Selected result file")
    if selected_result_directory_name is None:
        st.code("No result directory selected", language="text")
    else:
        result_path = result_path_for_graph(Path(graph_path), selected_result_directory_name)
        st.code(result_path.relative_to(results_root().parent).as_posix(), language="text")
        if solution is None:
            st.caption("This result directory does not contain a matching file for the selected graph.")

instance = load_instance(graph_path)
base_graph = build_graph(instance)
solution_analysis = (
    analyze_solution(instance, base_graph, solution) if solution is not None else None
)

graph_html, graph = render_interactive_graph(
    instance,
    show_edge_weights=show_edge_weights,
    show_reward_labels=show_reward_labels,
    physics_solver=physics_solver,
    repulsion_strength=repulsion_strength,
    spring_length=spring_length,
    spring_stiffness=spring_stiffness,
    damping=damping,
    node_spacing=node_spacing,
    show_solution_overlay=show_solution_overlay,
    solution=solution,
    solution_analysis=solution_analysis,
)

components_count = nx.number_connected_components(graph)
reward_df = pd.DataFrame(
    {
        "Node": list(instance.reward_by_node.keys()),
        "Reward": list(instance.reward_by_node.values()),
        "Degree": [graph.degree(node) for node in instance.reward_by_node],
        "Visited": [
            solution_analysis is not None and node in solution_analysis.visited_nodes
            for node in instance.reward_by_node
        ],
        "Visit order": [
            solution_analysis.visit_order_by_node.get(node) if solution_analysis is not None else None
            for node in instance.reward_by_node
        ],
    }
)
edge_df = pd.DataFrame(
    {
        "Source": [edge.source for edge in instance.edges],
        "Target": [edge.target for edge in instance.edges],
        "Weight": [edge.weight for edge in instance.edges],
        "On route": [
            solution_analysis is not None
            and normalize_edge(edge.source, edge.target) in solution_analysis.edge_steps_by_key
            for edge in instance.edges
        ],
        "Route steps": [
            ", ".join(
                str(step)
                for step in solution_analysis.edge_steps_by_key.get(
                    normalize_edge(edge.source, edge.target), ()
                )
            )
            if solution_analysis is not None
            else ""
            for edge in instance.edges
        ],
    }
)
solution_step_df = (
    build_solution_step_frame(graph, solution) if solution is not None else pd.DataFrame()
)

metric_columns = st.columns(5)
metric_columns[0].metric("Nodes", instance.node_count)
metric_columns[1].metric("Edges", instance.edge_count)
metric_columns[2].metric("Total reward pool", instance.total_reward)
metric_columns[3].metric("Avg. edge weight", f"{instance.average_edge_weight:.2f}")
metric_columns[4].metric("Components", components_count)

if solution is not None:
    solution_metrics = st.columns(4)
    solution_metrics[0].metric("Tour reward", solution.total_reward)
    solution_metrics[1].metric("Tour cost", solution.total_cost)
    solution_metrics[2].metric(
        "Unique visited nodes",
        len(solution_analysis.visited_nodes) if solution_analysis is not None else 0,
    )
    solution_metrics[3].metric("Route hops", max(len(solution.route) - 1, 0))

left_column, right_column = st.columns([1.8, 1.0])

with left_column:
    st.subheader("Interactive graph")
    if show_solution_overlay and solution is not None:
        st.caption(
            "Drag nodes, zoom with the mouse wheel, and hover for details. Red edges and blue-bordered nodes show the stored tour."
        )
    else:
        st.caption(
            "Drag nodes, zoom with the mouse wheel, and hover any node or edge to inspect rewards and weights."
        )
    components.html(graph_html, height=780, scrolling=False)
    st.caption("Node 1 stays outlined in orange because the problem statement uses it as the tour's start/end point.")

with right_column:
    if selected_result_directory_name is None:
        st.subheader("Solution tour")
        st.info("Pick a result directory to overlay one of the stored solution sets.")
    elif solution is None:
        st.subheader("Solution tour")
        st.info(
            f"No matching solution file was found for this graph in `results/{selected_result_directory_name}`."
        )
    else:
        st.subheader("Solution tour")
        st.caption(f"Result directory: `{selected_result_directory_name}`")
        if solution_analysis is not None:
            problems = []
            if not solution_analysis.starts_at_depot:
                problems.append("route does not start at node 1")
            if not solution_analysis.ends_at_depot:
                problems.append("route does not end at node 1")
            if solution_analysis.invalid_nodes:
                problems.append(
                    "unknown node(s): "
                    + ", ".join(str(node) for node in solution_analysis.invalid_nodes)
                )
            if solution_analysis.invalid_edges:
                problems.append(
                    "missing edge(s): "
                    + ", ".join(
                        f"{source}-{target}"
                        for source, target in solution_analysis.invalid_edges
                    )
                )
            if not solution_analysis.reward_matches:
                problems.append(
                    f"stored reward {solution.total_reward} does not match computed reward {solution_analysis.computed_reward}"
                )
            if not solution_analysis.cost_matches and solution_analysis.computed_cost is not None:
                problems.append(
                    f"stored cost {solution.total_cost} does not match computed cost {solution_analysis.computed_cost}"
                )
            if solution_analysis.repeated_non_depot_nodes:
                problems.append(
                    "revisited non-depot node(s): "
                    + ", ".join(str(node) for node in solution_analysis.repeated_non_depot_nodes)
                )

            if problems:
                st.warning("Validation notes: " + " | ".join(problems))
            else:
                st.success("Stored solution validated against the selected graph.")

        st.code(" -> ".join(str(node) for node in solution.route), language="text")

    st.subheader("Reward profile")
    st.bar_chart(reward_df.set_index("Node")[["Reward"]], width="stretch")
    st.dataframe(
        reward_df.sort_values(
            ["Visited", "Visit order", "Reward", "Node"],
            ascending=[False, True, False, True],
            na_position="last",
        ),
        width="stretch",
        hide_index=True,
    )

tabs = st.tabs(
    [
        "Solution",
        "Edges",
        "Run comparison",
        "Raw instance",
        "Raw solution",
        "Result directories",
        "Collections",
    ]
)

with tabs[0]:
    st.subheader("Solution steps")
    if selected_result_directory_name is None:
        st.info("Pick a result directory to inspect a stored solution.")
    elif solution is None:
        st.info(
            f"No matching solution file was found for this graph in `results/{selected_result_directory_name}`."
        )
    else:
        st.dataframe(solution_step_df, width="stretch", hide_index=True)

with tabs[1]:
    st.subheader("Weighted edges")
    st.dataframe(
        edge_df.sort_values(
            ["On route", "Route steps", "Weight", "Source", "Target"],
            ascending=[False, True, False, True, True],
        ),
        width="stretch",
        hide_index=True,
    )

with tabs[2]:
    st.subheader("Run comparison for current graph")
    comparison_df = result_comparison_frame(
        instance=instance,
        graph=base_graph,
        graph_path=graph_path,
        selected_result_directory_name=selected_result_directory_name,
    )
    if comparison_df.empty:
        st.info("No matching result files were found for this graph.")
    else:
        st.dataframe(comparison_df, width="stretch", hide_index=True)
        st.caption("Rows are sorted by higher reward first, then lower cost.")

with tabs[3]:
    st.subheader("Raw graph file")
    st.code(Path(graph_path).read_text(encoding="utf-8"), language="text")

with tabs[4]:
    st.subheader("Raw solution file")
    if selected_result_directory_name is None:
        st.info("Pick a result directory to inspect a stored solution file.")
    elif solution is None:
        st.info(
            f"No matching solution file was found for this graph in `results/{selected_result_directory_name}`."
        )
    else:
        st.code(solution.path.read_text(encoding="utf-8"), language="text")

with tabs[5]:
    st.subheader("Available result directories")
    result_directory_summary_df = result_directory_summary_frame(
        collection_name=collection_name,
        graph_name=Path(graph_path).name,
        selected_result_directory_name=selected_result_directory_name,
    )
    if result_directory_summary_df.empty:
        st.info("No result directories were found for the selected dataset collection.")
    else:
        st.dataframe(result_directory_summary_df, width="stretch", hide_index=True)

with tabs[6]:
    st.subheader("Available collections")
    st.dataframe(collection_summary_frame(collections), width="stretch", hide_index=True)
