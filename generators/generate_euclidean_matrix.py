import argparse
import math
import random
from pathlib import Path


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Generate synthetic Euclidean complete-graph TTSP matrix instances."
    )
    parser.add_argument(
        "-n",
        "--samples",
        type=int,
        default=10,
        help="Number of instances to generate.",
    )
    parser.add_argument(
        "--nodes",
        type=int,
        required=True,
        help="Number of nodes per instance, including depot node 1.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where generated .txt files will be written.",
    )
    parser.add_argument(
        "--prefix",
        default="graph",
        help="Output file prefix.",
    )
    parser.add_argument(
        "--seed-base",
        type=int,
        default=1,
        help="Seed used for the first generated instance; incremented per sample.",
    )
    parser.add_argument(
        "--coordinate-max",
        type=int,
        default=1000,
        help="Coordinates are sampled uniformly from [0, coordinate_max].",
    )
    parser.add_argument(
        "--reward-min",
        type=int,
        default=1,
        help="Minimum reward for non-depot nodes.",
    )
    parser.add_argument(
        "--reward-max",
        type=int,
        default=100,
        help="Maximum reward for non-depot nodes.",
    )
    parser.add_argument(
        "--include-reference-budget",
        action="store_true",
        help="Write a comment with a nearest-neighbor reference budget suggestion. Algorithms ignore it.",
    )
    return parser


def validate_args(args):
    if args.samples <= 0:
        raise ValueError("--samples must be positive.")
    if args.nodes < 2:
        raise ValueError("--nodes must be at least 2.")
    if args.coordinate_max <= 0:
        raise ValueError("--coordinate-max must be positive.")
    if args.reward_min < 0 or args.reward_max < args.reward_min:
        raise ValueError("Reward bounds must satisfy 0 <= reward-min <= reward-max.")


def euclidean_weight(a, b):
    distance = math.dist(a, b)
    return max(1, int(round(distance)))


def weight_matrix(coordinates):
    matrix = []
    for source, source_point in enumerate(coordinates):
        row = []
        for target, target_point in enumerate(coordinates):
            if source == target:
                row.append(0)
            else:
                row.append(euclidean_weight(source_point, target_point))
        matrix.append(row)
    return matrix


def nearest_neighbor_tour_cost(matrix):
    current = 0
    unvisited = set(range(1, len(matrix)))
    cost = 0

    while unvisited:
        next_node = min(unvisited, key=lambda node: (matrix[current][node], node))
        cost += matrix[current][next_node]
        current = next_node
        unvisited.remove(next_node)

    return cost + matrix[current][0]


def generate_coordinates(rng, nodes, coordinate_max):
    coordinates = []
    used = set()
    while len(coordinates) < nodes:
        point = (rng.uniform(0, coordinate_max), rng.uniform(0, coordinate_max))
        key = (round(point[0], 6), round(point[1], 6))
        if key in used:
            continue
        coordinates.append(point)
        used.add(key)
    return coordinates


def generate_rewards(rng, nodes, reward_min, reward_max):
    return [0] + [rng.randint(reward_min, reward_max) for _ in range(nodes - 1)]


def format_instance(coordinates, rewards, matrix, seed, include_reference_budget):
    lines = [
        "# TTSP Euclidean complete-graph matrix instance",
        f"# seed: {seed}",
        "# depot: 1",
        "# L_max is not stored in this file; pass it with --budget when running algorithms.",
        "# coordinate rows: node x y",
    ]
    lines.extend(
        f"# coord {index} {x:.6f} {y:.6f}"
        for index, (x, y) in enumerate(coordinates, start=1)
    )
    if include_reference_budget:
        lines.append(f"# reference_nearest_neighbor_tour_cost: {nearest_neighbor_tour_cost(matrix)}")
    lines.extend(
        [
            "TTSP_MATRIX",
            str(len(coordinates)),
            " ".join(map(str, rewards)),
        ]
    )
    lines.extend(" ".join(map(str, row)) for row in matrix)
    return "\n".join(lines) + "\n"


def generate_instance(args, sample_index):
    seed = args.seed_base + sample_index - 1
    rng = random.Random(seed)
    coordinates = generate_coordinates(rng, args.nodes, args.coordinate_max)
    rewards = generate_rewards(rng, args.nodes, args.reward_min, args.reward_max)
    matrix = weight_matrix(coordinates)
    return seed, format_instance(
        coordinates,
        rewards,
        matrix,
        seed,
        args.include_reference_budget,
    )


def main():
    parser = argument_parser()
    args = parser.parse_args()
    validate_args(args)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for sample_index in range(1, args.samples + 1):
        _, contents = generate_instance(args, sample_index)
        path = args.output_dir / f"{args.prefix}_{sample_index:03d}.txt"
        path.write_text(contents, encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
