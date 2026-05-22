import argparse
from collections import Counter
from heapq import heappop, heappush
import sys
from pathlib import Path


def argument_parser():
    parser = argparse.ArgumentParser(description="Run the greedy approach.")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to an input file or a directory of input files.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Path to an output file, or an output directory when --input is a directory.",
    )
    parser.add_argument(
        "--budget",
        type=int,
        required=True,
        help="Maximum total travel cost allowed for the closed tour.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output for debugging purposes.",
    )
    return parser


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
    return sum(edge_weight(graph, walk[index], walk[index + 1]) for index in range(len(walk) - 1))


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


def greedy_algorithm(n, rewards, graph, budget, depot=1, verbose=False):
    if not 1 <= depot <= n:
        raise ValueError(f"Depot {depot} is outside the node range 1..{n}.")
    if budget < 0:
        raise ValueError("Budget must be non-negative.")

    distances, paths, path_counters = build_shortest_path_index(graph)
    tour = [depot]
    node_counts = tour_node_counts(tour, path_counters)
    total_cost = 0
    total_reward = collected_reward(node_counts, rewards, depot)
    iteration = 0

    while True:
        best_candidate = None

        for node in range(1, n + 1):
            if node in tour:
                continue

            for index, (left, right) in enumerate(cycle_segments(tour)):
                left_to_node = distances[left].get(node, float("inf"))
                node_to_right = distances[node].get(right, float("inf"))
                current_segment_cost = distances[left].get(right, float("inf"))

                if float("inf") in (left_to_node, node_to_right, current_segment_cost):
                    continue

                additional_cost = left_to_node + node_to_right - current_segment_cost
                new_total_cost = total_cost + additional_cost
                if new_total_cost > budget:
                    continue

                updated_counts = replace_segment_counts(
                    node_counts=node_counts,
                    old_counter=path_counters[left][right],
                    new_counters=(
                        path_counters[left][node],
                        path_counters[node][right],
                    ),
                )
                new_total_reward = collected_reward(updated_counts, rewards, depot)
                reward_gain = new_total_reward - total_reward
                if reward_gain <= 0:
                    continue

                candidate = {
                    "priority": candidate_priority(
                        reward_gain=reward_gain,
                        additional_cost=additional_cost,
                        node=node,
                    ),
                    "node": node,
                    "position": index + 1,
                    "additional_cost": additional_cost,
                    "reward_gain": reward_gain,
                    "node_counts": updated_counts,
                    "total_cost": new_total_cost,
                    "total_reward": new_total_reward,
                }
                if best_candidate is None or candidate["priority"] > best_candidate["priority"]:
                    best_candidate = candidate

        if best_candidate is None:
            break

        node = best_candidate["node"]
        position = best_candidate["position"]
        tour.insert(position, node)
        node_counts = best_candidate["node_counts"]
        total_cost = best_candidate["total_cost"]
        total_reward = best_candidate["total_reward"]
        iteration += 1

        if verbose:
            print(
                "Iteration "
                f"{iteration}: inserted node {node} at position {position}, "
                f"additional cost {best_candidate['additional_cost']}, "
                f"reward gain {best_candidate['reward_gain']}, "
                f"total cost {total_cost}, total reward {total_reward}"
            )

    walk = expanded_walk(tour, paths)
    validated_cost = walk_cost(walk, graph)
    validated_reward = walk_reward(walk, rewards, depot)

    if validated_cost != total_cost:
        raise ValueError(
            f"Internal error: computed cost {total_cost} does not match walk cost {validated_cost}."
        )
    if validated_reward != total_reward:
        raise ValueError(
            f"Internal error: computed reward {total_reward} does not match walk reward {validated_reward}."
        )

    return total_reward, total_cost, walk


def format_solution(total_reward, total_cost, tour):
    return f"{total_reward} {total_cost}\n{' '.join(map(str, tour))}\n"


def solve_instance(input_path, budget, verbose=False):
    n, _, rewards, graph = read_input(input_path, verbose=verbose)
    total_reward, total_cost, tour = greedy_algorithm(
        n,
        rewards,
        graph,
        budget=budget,
        verbose=verbose,
    )
    return format_solution(total_reward, total_cost, tour)


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


if __name__ == "__main__":
    parser = argument_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None

    if not input_path.exists():
        print(f"Input path {input_path} does not exist.", file=sys.stderr)
        raise SystemExit(1)

    try:
        if input_path.is_dir():
            if output_path is None:
                raise ValueError("--output is required when --input is a directory.")

            validate_directory_output(output_path)

            for instance_path in input_files_from_directory(input_path):
                solution = solve_instance(
                    instance_path,
                    budget=args.budget,
                    verbose=args.verbose,
                )
                (output_path / instance_path.name).write_text(solution, encoding="utf-8")
        else:
            solution = solve_instance(
                input_path,
                budget=args.budget,
                verbose=args.verbose,
            )

            if output_path is None:
                sys.stdout.write(solution)
            else:
                destination = output_file_for_single_input(input_path, output_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(solution, encoding="utf-8")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
