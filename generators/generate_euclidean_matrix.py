import argparse
import math
import random
from pathlib import Path


SCENARIO_PRESETS = {
    "uniform_random_depot": {
        "geometry": "uniform",
        "depot_position": "random",
        "reward_pattern": "uniform",
    },
    "uniform_center_depot": {
        "geometry": "uniform",
        "depot_position": "center",
        "reward_pattern": "uniform",
    },
    "uniform_corner_depot": {
        "geometry": "uniform",
        "depot_position": "corner",
        "reward_pattern": "uniform",
    },
    "clustered_center_depot": {
        "geometry": "clustered",
        "depot_position": "center",
        "reward_pattern": "uniform",
        "clusters": 4,
    },
    "clustered_offset_depot": {
        "geometry": "clustered",
        "depot_position": "near_cluster",
        "reward_pattern": "uniform",
        "clusters": 4,
    },
    "clustered_outliers": {
        "geometry": "clustered_outliers",
        "depot_position": "center",
        "reward_pattern": "uniform",
        "clusters": 4,
        "outlier_fraction": 0.1,
    },
    "corridor": {
        "geometry": "corridor",
        "depot_position": "corridor_start",
        "reward_pattern": "uniform",
    },
    "ring": {
        "geometry": "ring",
        "depot_position": "center",
        "reward_pattern": "uniform",
    },
    "reward_near_depot": {
        "geometry": "uniform",
        "depot_position": "center",
        "reward_pattern": "near_depot",
    },
    "reward_far_from_depot": {
        "geometry": "uniform",
        "depot_position": "center",
        "reward_pattern": "far_from_depot",
    },
    "reward_cluster_hotspot": {
        "geometry": "clustered",
        "depot_position": "center",
        "reward_pattern": "cluster_hotspot",
        "clusters": 4,
    },
}

GEOMETRIES = ["uniform", "clustered", "clustered_outliers", "corridor", "ring"]
DEPOT_POSITIONS = ["random", "center", "corner", "near_cluster", "corridor_start"]
REWARD_PATTERNS = ["uniform", "near_depot", "far_from_depot", "cluster_hotspot"]
DEFAULT_SCENARIO = "uniform_random_depot"


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
        help="Coordinates are generated inside [0, coordinate_max].",
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIO_PRESETS),
        default=DEFAULT_SCENARIO,
        help="Readable preset combining coordinate geometry, depot placement, and reward pattern.",
    )
    parser.add_argument(
        "--geometry",
        choices=GEOMETRIES,
        help="Override the scenario coordinate geometry.",
    )
    parser.add_argument(
        "--depot-position",
        choices=DEPOT_POSITIONS,
        help="Override where depot node 1 is placed in the coordinate space.",
    )
    parser.add_argument(
        "--reward-pattern",
        choices=REWARD_PATTERNS,
        help="Override how non-depot rewards relate to the generated coordinates.",
    )
    parser.add_argument(
        "--clusters",
        type=int,
        help="Number of clusters for clustered geometries.",
    )
    parser.add_argument(
        "--cluster-spread-ratio",
        type=float,
        help="Cluster standard deviation as a fraction of coordinate_max.",
    )
    parser.add_argument(
        "--outlier-fraction",
        type=float,
        help="Fraction of non-depot nodes sampled uniformly for clustered_outliers geometry.",
    )
    parser.add_argument(
        "--corridor-width-ratio",
        type=float,
        help="Corridor standard deviation as a fraction of coordinate_max.",
    )
    parser.add_argument(
        "--ring-radius-ratio",
        type=float,
        help="Mean ring radius as a fraction of coordinate_max.",
    )
    parser.add_argument(
        "--ring-noise-ratio",
        type=float,
        help="Ring radial standard deviation as a fraction of coordinate_max.",
    )
    parser.add_argument(
        "--hotspot-cluster",
        type=int,
        help="One-based cluster index receiving higher rewards for cluster_hotspot rewards.",
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


def resolve_settings(args):
    settings = {
        "scenario": args.scenario,
        "coordinate_max": args.coordinate_max,
        "geometry": "uniform",
        "depot_position": "random",
        "reward_pattern": "uniform",
        "clusters": 4,
        "cluster_spread_ratio": 0.08,
        "outlier_fraction": 0.1,
        "corridor_width_ratio": 0.08,
        "ring_radius_ratio": 0.35,
        "ring_noise_ratio": 0.05,
        "hotspot_cluster": 1,
    }
    settings.update(SCENARIO_PRESETS[args.scenario])

    overrides = {
        "geometry": args.geometry,
        "depot_position": args.depot_position,
        "reward_pattern": args.reward_pattern,
        "clusters": args.clusters,
        "cluster_spread_ratio": args.cluster_spread_ratio,
        "outlier_fraction": args.outlier_fraction,
        "corridor_width_ratio": args.corridor_width_ratio,
        "ring_radius_ratio": args.ring_radius_ratio,
        "ring_noise_ratio": args.ring_noise_ratio,
        "hotspot_cluster": args.hotspot_cluster,
    }
    settings.update({key: value for key, value in overrides.items() if value is not None})

    if settings["clusters"] < 1:
        raise ValueError("--clusters must be positive.")
    if settings["cluster_spread_ratio"] <= 0:
        raise ValueError("--cluster-spread-ratio must be positive.")
    if not 0 <= settings["outlier_fraction"] < 1:
        raise ValueError("--outlier-fraction must satisfy 0 <= value < 1.")
    if settings["corridor_width_ratio"] <= 0:
        raise ValueError("--corridor-width-ratio must be positive.")
    if settings["ring_radius_ratio"] <= 0:
        raise ValueError("--ring-radius-ratio must be positive.")
    if settings["ring_noise_ratio"] <= 0:
        raise ValueError("--ring-noise-ratio must be positive.")
    if not 1 <= settings["hotspot_cluster"] <= settings["clusters"]:
        raise ValueError("--hotspot-cluster must be in the range 1..clusters.")
    if (
        settings["depot_position"] == "near_cluster"
        and settings["geometry"] not in {"clustered", "clustered_outliers"}
    ):
        raise ValueError("near_cluster depot placement requires clustered geometry.")
    if (
        settings["reward_pattern"] == "cluster_hotspot"
        and settings["geometry"] not in {"clustered", "clustered_outliers"}
    ):
        raise ValueError("cluster_hotspot rewards require clustered geometry.")

    return settings


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


def clamp(value, low, high):
    return max(low, min(high, value))


def unique_key(point):
    return (round(point[0], 6), round(point[1], 6))


def bounded_point(point, coordinate_max):
    return (
        clamp(point[0], 0, coordinate_max),
        clamp(point[1], 0, coordinate_max),
    )


def append_unique(coordinates, cluster_ids, used, point, cluster_id, coordinate_max):
    point = bounded_point(point, coordinate_max)
    key = unique_key(point)
    if key in used:
        return False
    coordinates.append(point)
    cluster_ids.append(cluster_id)
    used.add(key)
    return True


def random_point(rng, coordinate_max):
    return (rng.uniform(0, coordinate_max), rng.uniform(0, coordinate_max))


def depot_coordinate(rng, coordinate_max, position, cluster_centers=None):
    center = coordinate_max / 2
    if position == "random":
        return random_point(rng, coordinate_max)
    if position == "center":
        return (center, center)
    if position == "corner":
        margin = coordinate_max * 0.08
        return (margin, margin)
    if position == "near_cluster":
        if not cluster_centers:
            raise ValueError("near_cluster depot placement requires clustered geometry.")
        return cluster_centers[0]
    if position == "corridor_start":
        return (coordinate_max * 0.05, center)
    raise ValueError(f"Unsupported depot position: {position}")


def generate_cluster_centers(rng, clusters, coordinate_max):
    margin = coordinate_max * 0.15
    if clusters == 1:
        return [(coordinate_max / 2, coordinate_max / 2)]
    return [
        (
            rng.uniform(margin, coordinate_max - margin),
            rng.uniform(margin, coordinate_max - margin),
        )
        for _ in range(clusters)
    ]


def generate_coordinates(rng, nodes, coordinate_max, settings):
    coordinates = []
    cluster_ids = []
    used = set()

    geometry = settings["geometry"]
    cluster_centers = None
    if geometry in {"clustered", "clustered_outliers"}:
        cluster_centers = generate_cluster_centers(
            rng,
            settings["clusters"],
            coordinate_max,
        )

    depot = depot_coordinate(
        rng,
        coordinate_max,
        settings["depot_position"],
        cluster_centers,
    )
    append_unique(coordinates, cluster_ids, used, depot, None, coordinate_max)

    while len(coordinates) < nodes:
        node_index = len(coordinates)
        cluster_id = None

        if geometry == "uniform":
            point = random_point(rng, coordinate_max)
        elif geometry in {"clustered", "clustered_outliers"}:
            sample_outlier = (
                geometry == "clustered_outliers"
                and rng.random() < settings["outlier_fraction"]
            )
            if sample_outlier:
                point = random_point(rng, coordinate_max)
            else:
                cluster_id = (node_index - 1) % settings["clusters"]
                center = cluster_centers[cluster_id]
                spread = coordinate_max * settings["cluster_spread_ratio"]
                point = (
                    rng.gauss(center[0], spread),
                    rng.gauss(center[1], spread),
                )
        elif geometry == "corridor":
            center_y = coordinate_max / 2
            spread = coordinate_max * settings["corridor_width_ratio"]
            point = (rng.uniform(0, coordinate_max), rng.gauss(center_y, spread))
        elif geometry == "ring":
            center = coordinate_max / 2
            angle = rng.uniform(0, 2 * math.pi)
            radius = rng.gauss(
                coordinate_max * settings["ring_radius_ratio"],
                coordinate_max * settings["ring_noise_ratio"],
            )
            point = (
                center + radius * math.cos(angle),
                center + radius * math.sin(angle),
            )
        else:
            raise ValueError(f"Unsupported geometry: {geometry}")

        append_unique(coordinates, cluster_ids, used, point, cluster_id, coordinate_max)

    metadata = {
        "cluster_ids": cluster_ids,
        "cluster_centers": cluster_centers or [],
    }
    return coordinates, metadata


def scaled_reward(rng, reward_min, reward_max, signal):
    if reward_min == reward_max:
        return reward_min
    noisy_signal = clamp(signal + rng.uniform(-0.12, 0.12), 0, 1)
    return int(round(reward_min + noisy_signal * (reward_max - reward_min)))


def generate_rewards(rng, coordinates, metadata, reward_min, reward_max, settings):
    rewards = [0]
    pattern = settings["reward_pattern"]
    depot = coordinates[0]
    distances = [math.dist(depot, point) for point in coordinates]
    max_distance = max(distances[1:], default=1) or 1
    hotspot_cluster_id = settings["hotspot_cluster"] - 1

    for node_index in range(1, len(coordinates)):
        if pattern == "uniform":
            rewards.append(rng.randint(reward_min, reward_max))
        elif pattern == "near_depot":
            signal = 1 - distances[node_index] / max_distance
            rewards.append(scaled_reward(rng, reward_min, reward_max, signal))
        elif pattern == "far_from_depot":
            signal = distances[node_index] / max_distance
            rewards.append(scaled_reward(rng, reward_min, reward_max, signal))
        elif pattern == "cluster_hotspot":
            cluster_id = metadata["cluster_ids"][node_index]
            signal = (
                rng.uniform(0.7, 1.0)
                if cluster_id == hotspot_cluster_id
                else rng.uniform(0.0, 0.45)
            )
            rewards.append(scaled_reward(rng, reward_min, reward_max, signal))
        else:
            raise ValueError(f"Unsupported reward pattern: {pattern}")

    return rewards


def setting_comments(settings):
    comments = [
        f"# scenario: {settings['scenario']}",
        f"# coordinate_max: {settings['coordinate_max']}",
        f"# geometry: {settings['geometry']}",
        f"# depot_position: {settings['depot_position']}",
        f"# reward_pattern: {settings['reward_pattern']}",
    ]
    if settings["geometry"] in {"clustered", "clustered_outliers"}:
        comments.extend(
            [
                f"# clusters: {settings['clusters']}",
                f"# cluster_spread_ratio: {settings['cluster_spread_ratio']}",
            ]
        )
    if settings["geometry"] == "clustered_outliers":
        comments.append(f"# outlier_fraction: {settings['outlier_fraction']}")
    if settings["geometry"] == "corridor":
        comments.append(f"# corridor_width_ratio: {settings['corridor_width_ratio']}")
    if settings["geometry"] == "ring":
        comments.extend(
            [
                f"# ring_radius_ratio: {settings['ring_radius_ratio']}",
                f"# ring_noise_ratio: {settings['ring_noise_ratio']}",
            ]
        )
    if settings["reward_pattern"] == "cluster_hotspot":
        comments.append(f"# hotspot_cluster: {settings['hotspot_cluster']}")
    return comments


def format_instance(coordinates, rewards, matrix, seed, include_reference_budget, settings):
    lines = [
        "# TTSP Euclidean complete-graph matrix instance",
        f"# seed: {seed}",
        "# depot: 1",
        "# L_max is not stored in this file; pass it with --budget when running algorithms.",
        "# coordinate rows: node x y",
    ]
    lines.extend(setting_comments(settings))
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
    settings = resolve_settings(args)
    coordinates, metadata = generate_coordinates(
        rng,
        args.nodes,
        args.coordinate_max,
        settings,
    )
    rewards = generate_rewards(
        rng,
        coordinates,
        metadata,
        args.reward_min,
        args.reward_max,
        settings,
    )
    matrix = weight_matrix(coordinates)
    return seed, format_instance(
        coordinates,
        rewards,
        matrix,
        seed,
        args.include_reference_budget,
        settings,
    )


def main():
    parser = argument_parser()
    args = parser.parse_args()
    validate_args(args)
    resolve_settings(args)

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
