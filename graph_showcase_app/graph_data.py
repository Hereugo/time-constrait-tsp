from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Edge:
    source: int
    target: int
    weight: int


@dataclass(frozen=True)
class GraphInstance:
    path: Path
    collection: str
    name: str
    node_count: int
    edge_count: int
    rewards: tuple[int, ...]
    edges: tuple[Edge, ...]

    @property
    def reward_by_node(self) -> dict[int, int]:
        return {node: reward for node, reward in enumerate(self.rewards, start=1)}

    @property
    def total_reward(self) -> int:
        return sum(self.rewards)

    @property
    def min_reward(self) -> int:
        return min(self.rewards)

    @property
    def max_reward(self) -> int:
        return max(self.rewards)

    @property
    def average_reward(self) -> float:
        return self.total_reward / self.node_count

    @property
    def total_edge_weight(self) -> int:
        return sum(edge.weight for edge in self.edges)

    @property
    def average_edge_weight(self) -> float:
        if not self.edges:
            return 0.0
        return self.total_edge_weight / self.edge_count


@dataclass(frozen=True)
class SolutionInstance:
    path: Path
    collection: str
    name: str
    total_reward: int
    total_cost: int
    route: tuple[int, ...]

    @property
    def route_edges(self) -> tuple[tuple[int, int], ...]:
        return tuple(zip(self.route, self.route[1:]))

    @property
    def unique_route_nodes(self) -> tuple[int, ...]:
        nodes = self.route
        if len(nodes) > 1 and nodes[0] == nodes[-1]:
            nodes = nodes[:-1]

        ordered_nodes: list[int] = []
        seen: set[int] = set()
        for node in nodes:
            if node in seen:
                continue
            seen.add(node)
            ordered_nodes.append(node)
        return tuple(ordered_nodes)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def datasets_root() -> Path:
    return repo_root() / "datasets"


def results_root() -> Path:
    return repo_root() / "results"


def list_dataset_collections() -> dict[str, list[Path]]:
    collections: dict[str, list[Path]] = {}
    base_dir = datasets_root()

    if not base_dir.exists():
        return collections

    for collection_dir in sorted(base_dir.iterdir()):
        if not collection_dir.is_dir():
            continue

        graph_files = sorted(collection_dir.glob("*.txt"))
        if graph_files:
            collections[collection_dir.name] = graph_files

    return collections


def list_result_directories() -> dict[str, list[Path]]:
    directories: dict[str, list[Path]] = {}
    base_dir = results_root()

    if not base_dir.exists():
        return directories

    for result_dir in sorted(base_dir.iterdir()):
        if not result_dir.is_dir():
            continue

        result_files = sorted(result_dir.glob("*.txt"))
        if result_files:
            directories[result_dir.name] = result_files

    return directories


def list_result_directories_for_collection(collection_name: str) -> dict[str, list[Path]]:
    matching_directories: dict[str, list[Path]] = {}
    for directory_name, result_files in list_result_directories().items():
        if directory_name == collection_name or directory_name.startswith(f"{collection_name}_"):
            matching_directories[directory_name] = result_files
    return matching_directories


def load_graph_instance(path: Path) -> GraphInstance:
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    if len(lines) < 2:
        raise ValueError(f"{path} does not contain enough data for a graph instance.")

    try:
        node_count, edge_count = map(int, lines[0].split())
    except ValueError as exc:
        raise ValueError(f"Invalid header in {path}: {lines[0]!r}") from exc

    rewards = tuple(int(value) for value in lines[1].split())
    if len(rewards) != node_count:
        raise ValueError(
            f"{path} declares {node_count} nodes but contains {len(rewards)} rewards."
        )

    edge_lines = lines[2:]
    if len(edge_lines) != edge_count:
        raise ValueError(
            f"{path} declares {edge_count} edges but contains {len(edge_lines)} edge rows."
        )

    edges: list[Edge] = []
    for line_number, row in enumerate(edge_lines, start=3):
        parts = row.split()
        if len(parts) != 3:
            raise ValueError(f"Invalid edge row at {path}:{line_number}: {row!r}")

        source, target, weight = map(int, parts)
        edges.append(Edge(source=source, target=target, weight=weight))

    return GraphInstance(
        path=path,
        collection=path.parent.name,
        name=path.name,
        node_count=node_count,
        edge_count=edge_count,
        rewards=rewards,
        edges=tuple(edges),
    )


def load_solution_instance(path: Path) -> SolutionInstance:
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    if len(lines) < 2:
        raise ValueError(f"{path} does not contain enough data for a solution instance.")

    try:
        total_reward, total_cost = map(int, lines[0].split())
    except ValueError as exc:
        raise ValueError(f"Invalid solution header in {path}: {lines[0]!r}") from exc

    try:
        route = tuple(int(value) for value in lines[1].split())
    except ValueError as exc:
        raise ValueError(f"Invalid route row in {path}: {lines[1]!r}") from exc

    if not route:
        raise ValueError(f"{path} does not contain a route.")

    return SolutionInstance(
        path=path,
        collection=path.parent.name,
        name=path.name,
        total_reward=total_reward,
        total_cost=total_cost,
        route=route,
    )


def result_path_for_graph(graph_path: Path, result_directory_name: str) -> Path:
    return results_root() / result_directory_name / graph_path.name


def load_solution_for_graph(
    graph_path: Path,
    result_directory_name: str | None,
) -> SolutionInstance | None:
    if result_directory_name is None:
        return None

    solution_path = result_path_for_graph(graph_path, result_directory_name)
    if not solution_path.exists():
        return None
    return load_solution_instance(solution_path)
