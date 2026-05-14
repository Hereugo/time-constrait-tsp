#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./generate.sh --samples N [options] -- <rudy graph expression>

Generates graph instance files by:
1. calling Rudy to create the graph topology and weights
2. attaching a seeded random reward as a fourth column on each edge

Output format:
  n m
  u v w r
  ...

Options:
  -n, --samples N            Number of graph instances to generate
  -o, -d, --dir, --output-dir DIR
                             Output directory (default: ./generated)
  --prefix NAME              Output file prefix (default: graph)
  --reward-seed-base SEED    Base seed for rewards (default: 2000)
  --graph-seed-base SEED     Base seed for Rudy placeholder replacement (default: 3000)
  --reward-min VALUE         Minimum reward value (default: 1)
  --reward-max VALUE         Maximum reward value (default: 100)
  -h, --help                 Show this help

Notes:
  - Everything after '--' is passed directly to Rudy.
  - Use the token '__SEED__' inside the Rudy expression if you want the
    graph seed to vary per sample.
  - Example:
      ./generate.sh -n 3 --reward-min 5 --reward-max 20 -- \
        -planar 25 40 __SEED__
EOF
}

require_int() {
  local name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^-?[0-9]+$ ]]; then
    printf 'Invalid integer for %s: %s\n' "$name" "$value" >&2
    exit 1
  fi
}

require_value() {
  local flag="$1"
  local value="${2:-}"
  if [[ -z "$value" ]]; then
    printf 'Missing value for %s\n' "$flag" >&2
    exit 1
  fi
}

samples=""
output_dir=""
prefix="graph"
reward_seed_base=2000
graph_seed_base=3000
reward_min=1
reward_max=100

while (($#)); do
  case "$1" in
    --samples=*)
      samples="${1#*=}"
      shift
      ;;
    -n|--samples)
      require_value "$1" "${2:-}"
      samples="${2:-}"
      shift 2
      ;;
    -o=*|-d=*|--dir=*|--output-dir=*)
      output_dir="${1#*=}"
      shift
      ;;
    -o|-d|--dir|--output-dir)
      require_value "$1" "${2:-}"
      output_dir="${2:-}"
      shift 2
      ;;
    --prefix=*)
      prefix="${1#*=}"
      shift
      ;;
    --prefix)
      require_value "$1" "${2:-}"
      prefix="${2:-}"
      shift 2
      ;;
    --reward-seed-base=*)
      reward_seed_base="${1#*=}"
      shift
      ;;
    --reward-seed-base)
      require_value "$1" "${2:-}"
      reward_seed_base="${2:-}"
      shift 2
      ;;
    --graph-seed-base=*)
      graph_seed_base="${1#*=}"
      shift
      ;;
    --graph-seed-base)
      require_value "$1" "${2:-}"
      graph_seed_base="${2:-}"
      shift 2
      ;;
    --reward-min=*)
      reward_min="${1#*=}"
      shift
      ;;
    --reward-min)
      require_value "$1" "${2:-}"
      reward_min="${2:-}"
      shift 2
      ;;
    --reward-max=*)
      reward_max="${1#*=}"
      shift
      ;;
    --reward-max)
      require_value "$1" "${2:-}"
      reward_max="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$samples" ]]; then
  printf 'Missing required option: --samples\n\n' >&2
  usage >&2
  exit 1
fi

if (($# == 0)); then
  printf 'Missing Rudy graph expression.\n\n' >&2
  usage >&2
  exit 1
fi

require_int "--samples" "$samples"
require_int "--reward-seed-base" "$reward_seed_base"
require_int "--graph-seed-base" "$graph_seed_base"
require_int "--reward-min" "$reward_min"
require_int "--reward-max" "$reward_max"

if ((samples <= 0)); then
  printf '--samples must be positive.\n' >&2
  exit 1
fi

if ((reward_min > reward_max)); then
  printf '--reward-min must be less than or equal to --reward-max.\n' >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rudy_dir="$script_dir/rudy"
rudy_bin="$rudy_dir/rudy"
output_dir="${output_dir:-$script_dir/generated}"

if [[ ! -x "$rudy_bin" ]]; then
  (
    cd "$rudy_dir"
    gcc gb_lib.c rudy.c -lm -o rudy
  )
fi

mkdir -p "$output_dir"

rudy_expr=("$@")

for ((sample_idx = 1; sample_idx <= samples; sample_idx++)); do
  graph_seed=$((graph_seed_base + sample_idx - 1))
  reward_seed=$((reward_seed_base + sample_idx - 1))

  sample_expr=()
  for token in "${rudy_expr[@]}"; do
    sample_expr+=("${token//__SEED__/$graph_seed}")
  done

  output_file="$(printf '%s/%s_%03d.txt' "$output_dir" "$prefix" "$sample_idx")"

  "$rudy_bin" "${sample_expr[@]}" | awk \
    -v reward_seed="$reward_seed" \
    -v reward_min="$reward_min" \
    -v reward_max="$reward_max" '
      function normalize_seed(seed, mod) {
        mod = 2147483647
        seed %= mod
        if (seed <= 0) {
          seed += mod - 1
        }
        return seed
      }

      function next_reward_rand() {
        reward_state = (reward_state * 48271) % 2147483647
        return reward_state / 2147483647
      }

      function random_reward(span) {
        span = reward_max - reward_min + 1
        return reward_min + int(next_reward_rand() * span)
      }

      BEGIN {
        reward_state = normalize_seed(reward_seed)
      }

      NR == 1 {
        n = $1
        m = $2
        print n, m
        next
      }

      NF >= 3 {
        u = $1
        v = $2
        w = $3
        r = random_reward()
        print u, v, w, r
      }
    ' > "$output_file"

  printf 'Wrote %s\n' "$output_file"
done
