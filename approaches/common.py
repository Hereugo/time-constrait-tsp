from collections import Counter
from heapq import heappop, heappush


def read_input(file_path, verbose=False):
    with open(file_path, "r") as f:
        data = f.read()
        lines = [line.strip() for line in data.splitlines() if line.strip()]
        if len(lines) < 2:
            raise ValueError("Input file must contain at least a header and reward line.")

        n, m = map(int, lines[0].split())
        if verbose:
            print(f"Node Count: {n}")
            print(f"Edge Count: {m}")

        rewards = list(map(int, lines[1].split()))
        if len(rewards) != n:
            raise ValueError(
                f"Input declares {n} nodes but contains {len(rewards)} rewards."
            )
        if verbose:
            print(f"Rewards: {rewards}")

        edge_lines = lines[2:]
        if len(edge_lines) != m:
            raise ValueError(
                f"Input declares {m} edges but contains {len(edge_lines)} edge rows."
            )

        graph = {node: {} for node in range(1, n + 1)}
        for line in edge_lines:
            u, v, w = map(int, line.split())
            if verbose:
                print(f"Edge: {u} - {v} (Weight: {w})")

            graph[u][v] = w
            graph[v][u] = w

    return n, m, rewards, graph


def edge_weight(graph, source, target):
    if source == target:
        return 0
    return graph.get(source, {}).get(target)


def insertion_score(reward_gain, additional_cost):
    if additional_cost <= 0:
        return float("inf")
    return reward_gain / additional_cost


def candidate_priority(reward_gain, additional_cost, node):
    return (
        insertion_score(reward_gain, additional_cost),
        reward_gain,
        -additional_cost,
        -node,
    )


def dijkstra_shortest_paths(graph, source):
    distances = {node: float("inf") for node in graph}
    predecessors = {source: None}
    distances[source] = 0
    queue = [(0, source)]

    while queue:
        current_distance, node = heappop(queue)
        if current_distance != distances[node]:
            continue

        for neighbor, weight in sorted(graph[node].items()):
            next_distance = current_distance + weight
            if next_distance < distances[neighbor]:
                distances[neighbor] = next_distance
                predecessors[neighbor] = node
                heappush(queue, (next_distance, neighbor))

    paths = {}
    for target, distance in distances.items():
        if distance == float("inf"):
            continue

        path = []
        current = target
        while current is not None:
            path.append(current)
            current = predecessors.get(current)

        paths[target] = list(reversed(path))

    return distances, paths


def build_shortest_path_index(graph):
    distances = {}
    paths = {}
    counters = {}

    for source in graph:
        source_distances, source_paths = dijkstra_shortest_paths(graph, source)
        distances[source] = source_distances
        paths[source] = source_paths
        counters[source] = {
            target: Counter(path_nodes) for target, path_nodes in source_paths.items()
        }

    return distances, paths, counters


def cycle_segments(tour):
    return [(tour[index], tour[(index + 1) % len(tour)]) for index in range(len(tour))]


def expanded_walk(tour, paths):
    walk = []
    for index, (source, target) in enumerate(cycle_segments(tour)):
        segment = paths[source][target]
        if index:
            segment = segment[1:]
        walk.extend(segment)
    return walk


def walk_cost(walk, graph):
    return sum(
        edge_weight(graph, walk[index], walk[index + 1])
        for index in range(len(walk) - 1)
    )


def walk_reward(walk, rewards, depot):
    visited = set(walk)
    visited.discard(depot)
    return sum(rewards[node - 1] for node in visited)


def tour_node_counts(tour, path_counters):
    node_counts = Counter()
    for source, target in cycle_segments(tour):
        node_counts.update(path_counters[source][target])
    return node_counts


def collected_reward(node_counts, rewards, depot):
    return sum(
        rewards[node - 1]
        for node, count in node_counts.items()
        if node != depot and count > 0
    )


def replace_segment_counts(node_counts, old_counter, new_counters):
    updated_counts = node_counts.copy()
    updated_counts.subtract(old_counter)

    for counter in new_counters:
        updated_counts.update(counter)

    for node in list(updated_counts):
        if updated_counts[node] <= 0:
            del updated_counts[node]

    return updated_counts


def format_solution(total_reward, total_cost, tour):
    return f"{total_reward} {total_cost}\n{' '.join(map(str, tour))}\n"


def input_files_from_directory(input_dir):
    files = sorted(
        path for path in input_dir.iterdir() if path.is_file() and not path.name.startswith(".")
    )
    if not files:
        raise ValueError(f"Input directory {input_dir} does not contain any files.")
    return files


def output_file_for_single_input(input_path, output_path):
    if output_path.exists() and output_path.is_dir():
        return output_path / input_path.name
    return output_path


def validate_directory_output(output_path):
    if output_path.exists() and not output_path.is_dir():
        raise ValueError(
            f"Output path {output_path} must be a directory when the input is a directory."
        )
    output_path.mkdir(parents=True, exist_ok=True)
