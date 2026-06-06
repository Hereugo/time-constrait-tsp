import argparse
import subprocess
import sys
from pathlib import Path


def argument_parser():
    parser = argparse.ArgumentParser(description="Run several GA result batches.")
    parser.add_argument(
        "--input",
        required=True,
        help="Dataset collection directory, for example datasets/custom.",
    )
    parser.add_argument(
        "--budget",
        type=int,
        required=True,
        help="Maximum total travel cost allowed for each tour.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        required=True,
        help="One or more seeds to run as separate batches.",
    )
    parser.add_argument("--generations", type=int, default=100)
    parser.add_argument("--population-size", type=int, default=50)
    parser.add_argument("--mutation-rate", type=float, default=0.1)
    parser.add_argument("--tournament-size", type=int, default=3)
    parser.add_argument("--elite-size", type=int, default=1)
    parser.add_argument(
        "--results-root",
        default="results",
        help="Root folder for normal two-line solution outputs.",
    )
    parser.add_argument(
        "--metadata-root",
        default="results_metadata/genetic",
        help="Root folder for optional GA JSON metadata outputs.",
    )
    parser.add_argument(
        "--run-prefix",
        default="ga",
        help="Label embedded in each result directory name.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to run approaches/genetic/index.py.",
    )
    return parser


def format_mutation_rate(value):
    return str(value).replace(".", "p")


def result_directory_name(collection, run_prefix, seed, generations, population_size, mutation_rate):
    mutation_label = format_mutation_rate(mutation_rate)
    return (
        f"{collection}_{run_prefix}"
        f"_seed{seed:03d}"
        f"_g{generations}"
        f"_p{population_size}"
        f"_m{mutation_label}"
    )


def main():
    parser = argument_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input path {input_path} does not exist.", file=sys.stderr)
        raise SystemExit(1)
    if not input_path.is_dir():
        print("GA batch input must be a dataset collection directory.", file=sys.stderr)
        raise SystemExit(1)

    script_path = Path(__file__).with_name("index.py")
    collection = input_path.name
    results_root = Path(args.results_root)
    metadata_root = Path(args.metadata_root)

    for seed in args.seeds:
        directory_name = result_directory_name(
            collection=collection,
            run_prefix=args.run_prefix,
            seed=seed,
            generations=args.generations,
            population_size=args.population_size,
            mutation_rate=args.mutation_rate,
        )
        output_dir = results_root / directory_name
        metadata_dir = metadata_root / directory_name

        command = [
            args.python,
            str(script_path),
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--metadata-output",
            str(metadata_dir),
            "--budget",
            str(args.budget),
            "--seed",
            str(seed),
            "--generations",
            str(args.generations),
            "--population-size",
            str(args.population_size),
            "--mutation-rate",
            str(args.mutation_rate),
            "--tournament-size",
            str(args.tournament_size),
            "--elite-size",
            str(args.elite_size),
        ]

        print(f"Running seed {seed}: {output_dir}")
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
