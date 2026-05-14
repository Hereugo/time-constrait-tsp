import argparse
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


def insertion_score(reward, additional_cost):
    if additional_cost <= 0:
        return float("inf")
    return reward / additional_cost


def candidate_priority(node_reward, additional_cost, node):
    return (
        insertion_score(node_reward, additional_cost),
        node_reward,
        -additional_cost,
        -node,
    )


def greedy_algorithm(n, rewards, graph, budget, depot=1, verbose=False):
    if not 1 <= depot <= n:
        raise ValueError(f"Depot {depot} is outside the node range 1..{n}.")
    if budget < 0:
        raise ValueError("Budget must be non-negative.")

    tour = [depot]
    visited = {depot}
    total_cost = 0
    total_reward = 0
    iteration = 0

    while True:
        best_candidate = None

        for node in range(1, n + 1):
            if node in visited:
                continue

            node_reward = rewards[node - 1]
            best_position = None
            best_additional_cost = None

            for index in range(len(tour)):
                left = tour[index]
                right = tour[(index + 1) % len(tour)]

                left_to_node = edge_weight(graph, left, node)
                node_to_right = edge_weight(graph, node, right)
                if left_to_node is None or node_to_right is None:
                    continue

                current_edge_cost = edge_weight(graph, left, right)
                if current_edge_cost is None:
                    continue

                additional_cost = left_to_node + node_to_right - current_edge_cost
                if best_additional_cost is None or additional_cost < best_additional_cost:
                    best_additional_cost = additional_cost
                    best_position = index + 1

            if best_position is None or best_additional_cost is None:
                continue

            new_total_cost = total_cost + best_additional_cost
            if new_total_cost > budget:
                continue

            candidate = {
                "priority": candidate_priority(
                    node_reward=node_reward,
                    additional_cost=best_additional_cost,
                    node=node,
                ),
                "node": node,
                "position": best_position,
                "additional_cost": best_additional_cost,
                "reward": node_reward,
            }
            if best_candidate is None or candidate["priority"] > best_candidate["priority"]:
                best_candidate = candidate

        if best_candidate is None:
            break

        node = best_candidate["node"]
        position = best_candidate["position"]
        additional_cost = best_candidate["additional_cost"]
        node_reward = best_candidate["reward"]

        tour.insert(position, node)
        visited.add(node)
        total_cost += additional_cost
        total_reward += node_reward
        iteration += 1

        if verbose:
            print(
                "Iteration "
                f"{iteration}: inserted node {node} at position {position}, "
                f"additional cost {additional_cost}, total cost {total_cost}, "
                f"total reward {total_reward}"
            )

    closed_tour = tour + [depot]
    return total_reward, total_cost, closed_tour


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
