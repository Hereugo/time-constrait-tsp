from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pandas as pd
from pyvis.network import Network
import streamlit as st
import streamlit.components.v1 as components

from graph_data import GraphInstance, datasets_root, list_dataset_collections, load_graph_instance


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
) -> tuple[str, nx.Graph]:
    graph = build_graph(instance)
    rewards = [graph.nodes[node]["reward"] for node in graph.nodes]
    weights = [graph.edges[edge]["weight"] for edge in graph.edges]

    reward_min = min(rewards) if rewards else 0
    reward_max = max(rewards) if rewards else 1

    node_sizes = scale_values(rewards, 18, 42)
    edge_widths = scale_values(weights, 1.5, 5.0)
    node_size_map = {node: size for node, size in zip(graph.nodes, node_sizes)}
    edge_width_map = {edge: width for edge, width in zip(graph.edges, edge_widths)}

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
        label = f"{node}\nR={reward}" if show_reward_labels else str(node)
        border_color = "#d97706" if node == 1 else "#0f172a"
        highlight_border = "#b45309" if node == 1 else "#1e293b"
        fill_color = interpolate_color(reward, reward_min, reward_max)
        title = (
            f"<strong>Node {node}</strong><br>"
            f"Reward: {reward}<br>"
            f"Degree: {degree}<br>"
            f"{'Start / end node' if node == 1 else 'Regular node'}"
        )

        network.add_node(
            node,
            label=label,
            title=title,
            size=node_size_map[node],
            borderWidth=4 if node == 1 else 1.5,
            color={
                "background": fill_color,
                "border": border_color,
                "highlight": {"background": fill_color, "border": highlight_border},
                "hover": {"background": fill_color, "border": highlight_border},
            },
        )

    for source, target in graph.edges:
        weight = graph.edges[source, target]["weight"]
        label = str(weight) if show_edge_weights else ""

        network.add_edge(
            source,
            target,
            label=label,
            title=f"Edge {source} - {target}<br>Weight: {weight}",
            width=edge_width_map[(source, target)],
            color={"color": "#64748b", "highlight": "#0f172a"},
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


collections = collection_index()

st.title("Time-Constrained TSP Graph Showcase")
st.caption(
    "Browse the dataset instances in `datasets/`, inspect weighted edges, and compare node rewards in an interactive force-directed graph."
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
    collection_name = st.selectbox("Dataset collection", list(collections))
    graph_path = st.selectbox(
        "Graph instance",
        collections[collection_name],
        format_func=lambda path_str: Path(path_str).name,
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
    st.write("Current file")
    st.code(Path(graph_path).relative_to(datasets_root().parent).as_posix(), language="text")

instance = load_instance(graph_path)
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
)

components_count = nx.number_connected_components(graph)
reward_df = pd.DataFrame(
    {
        "Node": list(instance.reward_by_node.keys()),
        "Reward": list(instance.reward_by_node.values()),
        "Degree": [graph.degree(node) for node in instance.reward_by_node],
    }
)
edge_df = pd.DataFrame(
    {
        "Source": [edge.source for edge in instance.edges],
        "Target": [edge.target for edge in instance.edges],
        "Weight": [edge.weight for edge in instance.edges],
    }
)

metric_columns = st.columns(5)
metric_columns[0].metric("Nodes", instance.node_count)
metric_columns[1].metric("Edges", instance.edge_count)
metric_columns[2].metric("Total reward", instance.total_reward)
metric_columns[3].metric("Avg. edge weight", f"{instance.average_edge_weight:.2f}")
metric_columns[4].metric("Components", components_count)

left_column, right_column = st.columns([1.8, 1.0])

with left_column:
    st.subheader("Interactive graph")
    st.caption(
        "Drag nodes, zoom with the mouse wheel, and hover any node or edge to inspect rewards and weights."
    )
    components.html(graph_html, height=780, scrolling=False)
    st.caption("Node 1 is outlined in orange because the problem statement uses it as the start/end point.")

with right_column:
    st.subheader("Reward profile")
    st.bar_chart(reward_df.set_index("Node")[["Reward"]], use_container_width=True)
    st.dataframe(
        reward_df.sort_values(["Reward", "Node"], ascending=[False, True]),
        use_container_width=True,
        hide_index=True,
    )

tabs = st.tabs(["Edges", "Raw instance", "Collections"])

with tabs[0]:
    st.subheader("Weighted edges")
    st.dataframe(
        edge_df.sort_values(["Weight", "Source", "Target"], ascending=[False, True, True]),
        use_container_width=True,
        hide_index=True,
    )

with tabs[1]:
    st.subheader("Raw file")
    st.code(Path(graph_path).read_text(encoding="utf-8"), language="text")

with tabs[2]:
    st.subheader("Available collections")
    st.dataframe(collection_summary_frame(collections), use_container_width=True, hide_index=True)
