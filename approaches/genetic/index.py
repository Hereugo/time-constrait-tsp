import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
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
    read_input_with_budget,
    replace_segment_counts,
    resolve_budget,
    tour_node_counts,
    validate_directory_output,
    walk_cost,
    walk_reward,
)


@dataclass(frozen=True)
class Individual:
    chromosome: tuple[int, ...]
    reward: int
    cost: int
    walk: tuple[int, ...]

    @property
    def fitness(self):
        return self.reward, -self.cost


def argument_parser():
    parser = argparse.ArgumentParser(description="Run the genetic algorithm approach.")
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
        "--metadata-output",
        type=str,
        help="Optional JSON metadata file or directory for GA run details.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=1,
        help="Random seed used for reproducible GA runs.",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=100,
        help="Number of generations to evolve after evaluating the initial population.",
    )
    parser.add_argument(
        "--population-size",
        type=int,
        default=50,
        help="Number of chromosomes in the population.",
    )
    parser.add_argument(
        "--mutation-rate",
        type=float,
        default=0.1,
        help="Probability of applying one swap mutation to each child.",
    )
    parser.add_argument(
        "--tournament-size",
        type=int,
        default=3,
        help="Number of individuals sampled for tournament selection.",
    )
    parser.add_argument(
        "--elite-size",
        type=int,
        default=1,
        help="Number of best individuals copied unchanged into each generation.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output for debugging purposes.",
    )
    return parser


def validate_ga_parameters(
    budget,
    population_size,
    generations,
    mutation_rate,
    tournament_size,
    elite_size,
):
    if budget < 0:
        raise ValueError("Budget must be non-negative.")
    if population_size <= 0:
        raise ValueError("Population size must be positive.")
    if generations < 0:
        raise ValueError("Generations must be non-negative.")
    if not 0 <= mutation_rate <= 1:
        raise ValueError("Mutation rate must be between 0 and 1.")
    if not 1 <= tournament_size <= population_size:
        raise ValueError("Tournament size must be between 1 and population size.")
    if not 0 <= elite_size <= population_size:
        raise ValueError("Elite size must be between 0 and population size.")


def best_insertion_for_node(
    node,
    tour,
    node_counts,
    total_cost,
    total_reward,
    rewards,
    budget,
    depot,
    distances,
    path_counters,
):
    best_candidate = None

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
            "position": index + 1,
            "node_counts": updated_counts,
            "total_cost": new_total_cost,
            "total_reward": new_total_reward,
            "additional_cost": additional_cost,
            "reward_gain": reward_gain,
        }
        if best_candidate is None or candidate["priority"] > best_candidate["priority"]:
            best_candidate = candidate

    return best_candidate


def decode_chromosome(
    chromosome,
    n,
    rewards,
    graph,
    budget,
    distances,
    paths,
    path_counters,
    depot=1,
    verbose=False,
):
    if not 1 <= depot <= n:
        raise ValueError(f"Depot {depot} is outside the node range 1..{n}.")

    tour = [depot]
    node_counts = tour_node_counts(tour, path_counters)
    total_cost = 0
    total_reward = collected_reward(node_counts, rewards, depot)

    for node in chromosome:
        if node in tour:
            continue

        best_candidate = best_insertion_for_node(
            node=node,
            tour=tour,
            node_counts=node_counts,
            total_cost=total_cost,
            total_reward=total_reward,
            rewards=rewards,
            budget=budget,
            depot=depot,
            distances=distances,
            path_counters=path_counters,
        )
        if best_candidate is None:
            continue

        tour.insert(best_candidate["position"], node)
        node_counts = best_candidate["node_counts"]
        total_cost = best_candidate["total_cost"]
        total_reward = best_candidate["total_reward"]

        if verbose:
            print(
                f"Decoded node {node}: additional cost {best_candidate['additional_cost']}, "
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

    return total_reward, total_cost, tuple(walk)


def greedy_seed_chromosome(
    n,
    rewards,
    budget,
    distances,
    path_counters,
    depot=1,
):
    tour = [depot]
    node_counts = tour_node_counts(tour, path_counters)
    total_cost = 0
    total_reward = collected_reward(node_counts, rewards, depot)
    inserted_order = []

    while True:
        best_candidate = None
        best_node = None

        for node in range(1, n + 1):
            if node in tour:
                continue

            candidate = best_insertion_for_node(
                node=node,
                tour=tour,
                node_counts=node_counts,
                total_cost=total_cost,
                total_reward=total_reward,
                rewards=rewards,
                budget=budget,
                depot=depot,
                distances=distances,
                path_counters=path_counters,
            )
            if candidate is None:
                continue
            if best_candidate is None or candidate["priority"] > best_candidate["priority"]:
                best_candidate = candidate
                best_node = node

        if best_candidate is None:
            break

        tour.insert(best_candidate["position"], best_node)
        node_counts = best_candidate["node_counts"]
        total_cost = best_candidate["total_cost"]
        total_reward = best_candidate["total_reward"]
        inserted_order.append(best_node)

    remaining = [node for node in range(1, n + 1) if node != depot and node not in inserted_order]
    return tuple(inserted_order + remaining)


def initial_population(base_chromosome, population_size, rng):
    population = [base_chromosome]
    genes = list(base_chromosome)

    while len(population) < population_size:
        chromosome = genes[:]
        rng.shuffle(chromosome)
        population.append(tuple(chromosome))

    return population


def order_crossover(parent_a, parent_b, rng):
    size = len(parent_a)
    if size <= 1:
        return tuple(parent_a)

    start, end = sorted(rng.sample(range(size), 2))
    child = [None] * size
    child[start : end + 1] = parent_a[start : end + 1]
    used = set(child[start : end + 1])
    fill_values = [gene for gene in parent_b if gene not in used]
    fill_index = 0

    for index in range(size):
        if child[index] is None:
            child[index] = fill_values[fill_index]
            fill_index += 1

    return tuple(child)


def mutate_swap(chromosome, mutation_rate, rng):
    if len(chromosome) <= 1 or rng.random() >= mutation_rate:
        return chromosome

    mutated = list(chromosome)
    left, right = rng.sample(range(len(mutated)), 2)
    mutated[left], mutated[right] = mutated[right], mutated[left]
    return tuple(mutated)


def evaluate_population(
    chromosomes,
    n,
    rewards,
    graph,
    budget,
    distances,
    paths,
    path_counters,
    depot,
):
    return [
        evaluate_chromosome(
            chromosome=chromosome,
            n=n,
            rewards=rewards,
            graph=graph,
            budget=budget,
            distances=distances,
            paths=paths,
            path_counters=path_counters,
            depot=depot,
        )
        for chromosome in chromosomes
    ]


def evaluate_chromosome(
    chromosome,
    n,
    rewards,
    graph,
    budget,
    distances,
    paths,
    path_counters,
    depot,
):
    reward, cost, walk = decode_chromosome(
        chromosome=chromosome,
        n=n,
        rewards=rewards,
        graph=graph,
        budget=budget,
        distances=distances,
        paths=paths,
        path_counters=path_counters,
        depot=depot,
    )
    return Individual(
        chromosome=tuple(chromosome),
        reward=reward,
        cost=cost,
        walk=walk,
    )


def best_individual(population):
    return max(population, key=lambda individual: individual.fitness)


def history_entry(generation, individual):
    return {
        "generation": generation,
        "best_reward": individual.reward,
        "best_cost": individual.cost,
    }


def tournament_select(population, tournament_size, rng):
    competitors = rng.sample(population, tournament_size)
    return best_individual(competitors)


def genetic_algorithm(
    n,
    rewards,
    graph,
    budget,
    seed=1,
    generations=100,
    population_size=50,
    mutation_rate=0.1,
    tournament_size=3,
    elite_size=1,
    depot=1,
    verbose=False,
):
    validate_ga_parameters(
        budget=budget,
        population_size=population_size,
        generations=generations,
        mutation_rate=mutation_rate,
        tournament_size=tournament_size,
        elite_size=elite_size,
    )

    rng = random.Random(seed)
    distances, paths, path_counters = build_shortest_path_index(graph)
    base_chromosome = greedy_seed_chromosome(
        n=n,
        rewards=rewards,
        budget=budget,
        distances=distances,
        path_counters=path_counters,
        depot=depot,
    )
    chromosomes = initial_population(base_chromosome, population_size, rng)
    population = evaluate_population(
        chromosomes=chromosomes,
        n=n,
        rewards=rewards,
        graph=graph,
        budget=budget,
        distances=distances,
        paths=paths,
        path_counters=path_counters,
        depot=depot,
    )
    history = [history_entry(0, best_individual(population))]

    for generation in range(1, generations + 1):
        ranked = sorted(population, key=lambda individual: individual.fitness, reverse=True)
        next_population = ranked[:elite_size]

        while len(next_population) < population_size:
            parent_a = tournament_select(population, tournament_size, rng)
            parent_b = tournament_select(population, tournament_size, rng)
            child_chromosome = order_crossover(parent_a.chromosome, parent_b.chromosome, rng)
            child_chromosome = mutate_swap(child_chromosome, mutation_rate, rng)
            next_population.append(
                evaluate_chromosome(
                    chromosome=child_chromosome,
                    n=n,
                    rewards=rewards,
                    graph=graph,
                    budget=budget,
                    distances=distances,
                    paths=paths,
                    path_counters=path_counters,
                    depot=depot,
                )
            )

        population = next_population
        generation_best = best_individual(population)
        history.append(history_entry(generation, generation_best))

        if verbose:
            print(
                f"Generation {generation}: best reward {generation_best.reward}, "
                f"best cost {generation_best.cost}"
            )

    best = best_individual(population)
    return best, history


def metadata_for_instance(
    input_path,
    best,
    history,
    runtime_seconds,
    seed,
    budget,
    generations,
    population_size,
    mutation_rate,
    tournament_size,
    elite_size,
):
    return {
        "input": str(input_path),
        "parameters": {
            "budget": budget,
            "seed": seed,
            "generations": generations,
            "population_size": population_size,
            "mutation_rate": mutation_rate,
            "tournament_size": tournament_size,
            "elite_size": elite_size,
        },
        "runtime_seconds": runtime_seconds,
        "reward": best.reward,
        "cost": best.cost,
        "route_hops": max(len(best.walk) - 1, 0),
        "best_reward": best.reward,
        "best_cost": best.cost,
        "best_route": list(best.walk),
        "best_chromosome": list(best.chromosome),
        "history": history,
    }


def solve_instance(
    input_path,
    budget,
    seed=1,
    generations=100,
    population_size=50,
    mutation_rate=0.1,
    tournament_size=3,
    elite_size=1,
    verbose=False,
):
    started_at = time.perf_counter()
    n, _, rewards, graph, file_budget = read_input_with_budget(input_path, verbose=verbose)
    budget = resolve_budget(budget, file_budget)
    best, history = genetic_algorithm(
        n=n,
        rewards=rewards,
        graph=graph,
        budget=budget,
        seed=seed,
        generations=generations,
        population_size=population_size,
        mutation_rate=mutation_rate,
        tournament_size=tournament_size,
        elite_size=elite_size,
        verbose=verbose,
    )
    runtime_seconds = time.perf_counter() - started_at
    solution = format_solution(best.reward, best.cost, best.walk)
    metadata = metadata_for_instance(
        input_path=input_path,
        best=best,
        history=history,
        runtime_seconds=runtime_seconds,
        seed=seed,
        budget=budget,
        generations=generations,
        population_size=population_size,
        mutation_rate=mutation_rate,
        tournament_size=tournament_size,
        elite_size=elite_size,
    )
    return solution, metadata


def metadata_file_for_input(input_path, metadata_output_path):
    if metadata_output_path.suffix == ".json":
        return metadata_output_path
    return metadata_output_path / f"{input_path.stem}.json"


def write_metadata(metadata_path, metadata):
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argument_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None
    metadata_output_path = Path(args.metadata_output) if args.metadata_output else None

    if not input_path.exists():
        print(f"Input path {input_path} does not exist.", file=sys.stderr)
        raise SystemExit(1)

    try:
        validate_ga_parameters(
            budget=args.budget,
            population_size=args.population_size,
            generations=args.generations,
            mutation_rate=args.mutation_rate,
            tournament_size=args.tournament_size,
            elite_size=args.elite_size,
        )

        if input_path.is_dir():
            if output_path is None:
                raise ValueError("--output is required when --input is a directory.")
            if metadata_output_path is not None and metadata_output_path.suffix == ".json":
                raise ValueError("--metadata-output must be a directory when --input is a directory.")

            validate_directory_output(output_path)
            if metadata_output_path is not None:
                validate_directory_output(metadata_output_path)

            for instance_path in input_files_from_directory(input_path):
                solution, metadata = solve_instance(
                    instance_path,
                    budget=args.budget,
                    seed=args.seed,
                    generations=args.generations,
                    population_size=args.population_size,
                    mutation_rate=args.mutation_rate,
                    tournament_size=args.tournament_size,
                    elite_size=args.elite_size,
                    verbose=args.verbose,
                )
                (output_path / instance_path.name).write_text(solution, encoding="utf-8")

                if metadata_output_path is not None:
                    write_metadata(
                        metadata_output_path / f"{instance_path.stem}.json",
                        metadata,
                    )
        else:
            solution, metadata = solve_instance(
                input_path,
                budget=args.budget,
                seed=args.seed,
                generations=args.generations,
                population_size=args.population_size,
                mutation_rate=args.mutation_rate,
                tournament_size=args.tournament_size,
                elite_size=args.elite_size,
                verbose=args.verbose,
            )

            if output_path is None:
                sys.stdout.write(solution)
            else:
                destination = output_file_for_single_input(input_path, output_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(solution, encoding="utf-8")

            if metadata_output_path is not None:
                write_metadata(
                    metadata_file_for_input(input_path, metadata_output_path),
                    metadata,
                )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
