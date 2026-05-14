import argparse
import os


def argument_parser():
    parser = argparse.ArgumentParser(description="Run the greedy approach.")
    parser.add_argument(
        "--input",
        type=str,
        help="Path to the input file containing the problem instance.",
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

        n, m = map(int, data.splitlines()[0].split())
        if verbose:
            print(f"Node Count: {n}")
            print(f"Edge Count: {m}")

        rewards = list(map(int, data.splitlines()[1].split()))
        if verbose:
            print(f"Rewards: {rewards}")

        graph = {}
        for line in data.splitlines()[2:]:
            u, v, w = map(int, line.split())
            if verbose:
                print(f"Edge: {u} - {v} (Weight: {w})")

            graph.setdefault(u, []).append((v, w))
            graph.setdefault(v, []).append((u, w))

    return n, m, rewards, graph


def greedy_algorithm(n, m, rewards, graph):
    pass  # Implement the greedy algorithm here


if __name__ == "__main__":
    parser = argument_parser()
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Input file {args.input} does not exist.")
        exit(1)

    # Here you would add the code to read the input file, implement the greedy algorithm,
    # and output the results. This is just a placeholder to indicate where that code would go.
    print(f"Running greedy approach with input file: {args.input}")

    n, m, rewards, graph = read_input(args.input, verbose=args.verbose)

    greedy_algorithm(n, m, rewards, graph)
