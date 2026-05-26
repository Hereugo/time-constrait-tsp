import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (  # noqa: E402
    build_shortest_path_index,
    candidate_priority,
    collected_reward,
    cycle_segments,
    expanded_walk,
    format_solution,
    input_files_from_directory,
    output_file_for_single_input,
    read_input,
    replace_segment_counts,
    tour_node_counts,
    validate_directory_output,
    walk_cost,
    walk_reward,
)


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
