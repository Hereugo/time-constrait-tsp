import argparse
import os
import sys


def argument_parser():
    parser = argparse.ArgumentParser(description="Run the greedy approach.")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the input file containing the problem instance.",
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


if __name__ == "__main__":
    parser = argument_parser()
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Input file {args.input} does not exist.", file=sys.stderr)
        raise SystemExit(1)

    try:
        n, _, rewards, graph = read_input(args.input, verbose=args.verbose)
        total_reward, total_cost, tour = greedy_algorithm(
            n,
            rewards,
            graph,
            budget=args.budget,
            verbose=args.verbose,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"{total_reward} {total_cost}")
    print(" ".join(map(str, tour)))
