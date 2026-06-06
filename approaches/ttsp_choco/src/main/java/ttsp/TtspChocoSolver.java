package ttsp;

import org.chocosolver.solver.Model;
import org.chocosolver.solver.Solver;
import org.chocosolver.solver.variables.BoolVar;
import org.chocosolver.solver.variables.IntVar;
import org.chocosolver.solver.constraints.extension.Tuples;
import org.chocosolver.solver.search.limits.FailCounter;
import org.chocosolver.solver.search.strategy.Search;

import java.util.*;
import java.io.*;

public final class TtspChocoSolver {

    private TtspChocoSolver() {
    }

    public static void main(String[] args) throws IOException {
        // --- Parse CLI arguments ---
        String inputFile  = null;
        String outputFile = null;
        int budget        = -1;
        int timeLimitSeconds = 30;

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "-i": inputFile  = args[++i]; break;
                case "-o": outputFile = args[++i]; break;
                case "-b": budget     = Integer.parseInt(args[++i]); break;
                case "-t": timeLimitSeconds = Integer.parseInt(args[++i]); break;
                default:
                    System.err.println("Unknown flag: " + args[i]);
                    printUsage();
                    System.exit(1);
            }
        }

        if (inputFile == null || budget < 0) {
            System.err.println("Error: -i and -b are required.");
            printUsage();
            System.exit(1);
        }

        // --- Read input ---
        Scanner sc = new Scanner(new File(inputFile));
        int N = sc.nextInt();
        int M = sc.nextInt();

        int[] rewards = new int[N];
        for (int i = 0; i < N; i++) rewards[i] = sc.nextInt();
        rewards[0] = 0; // depot has no reward

        final int INF = Integer.MAX_VALUE / 2;
        int[][] D = new int[N][N];
        for (int[] row : D) Arrays.fill(row, INF);
        for (int i = 0; i < N; i++) D[i][i] = 0;

        int maxEdge = 0;
        for (int k = 0; k < M; k++) {
            int u = sc.nextInt() - 1; // convert to 0-indexed
            int v = sc.nextInt() - 1;
            int w = sc.nextInt();
            D[u][v] = w;
            D[v][u] = w;
            maxEdge = Math.max(maxEdge, w);
        }
        sc.close();

        int totalMaxReward = Arrays.stream(rewards).sum();

        // --- Build model ---
        Model model = new Model("TTSP");

        IntVar[] succ    = model.intVarArray("succ", N, 0, N - 1);
        IntVar[] dist    = model.intVarArray("dist", N, 0, maxEdge);
        BoolVar[] collected = model.boolVarArray("collected", N);
        IntVar totCost   = model.intVar("totCost", 0, budget);
        IntVar totReward = model.intVar("totReward", 0, totalMaxReward);

        // Distance table per city (sparse edges + self-loop)
        for (int i = 0; i < N; i++) {
            Tuples tuples = new Tuples(true);
            tuples.add(i, 0); // self-loop: city not in tour
            for (int j = 0; j < N; j++) {
                if (j != i && D[i][j] < INF) {
                    tuples.add(j, D[i][j]);
                }
            }
            model.table(succ[i], dist[i], tuples).post();
        }

        // Sub-circuit: partial tour rooted at depot (city 0)
        model.subCircuit(succ, 0, model.intVar("tourSize", 1, N)).post();
        if (N > 1) {
            model.arithm(succ[0], "!=", 0).post();
        }

        // Budget
        model.sum(dist, "=", totCost).post();

        // collected[i] = 1 iff non-depot city i is in the tour.
        model.arithm(collected[0], "=", 0).post();
        for (int i = 1; i < N; i++) {
            model.reification(collected[i], model.arithm(succ[i], "!=", i));
        }

        // Weighted reward per city
        IntVar[] weightedRewards = new IntVar[N];
        for (int i = 0; i < N; i++) {
            weightedRewards[i] = model.intVar("wr_" + i, 0, rewards[i]);
            model.times(collected[i], model.intVar("r_" + i, rewards[i]), weightedRewards[i]).post();
        }
        model.sum(weightedRewards, "=", totReward).post();

        // Objective
        model.setObjective(Model.MAXIMIZE, totReward);

        int[] greedySucc = greedyWarmStart(N, D, rewards, budget, INF);
        int greedyReward = greedySucc == null ? -1 : rewardOf(greedySucc, rewards);
        int greedyCost = greedySucc == null ? -1 : costOf(greedySucc, D);
        if (greedyReward > 0) {
            model.arithm(totReward, ">=", greedyReward).post();
        }

        // Reward-driven search strategy. Prefer the greedy warm-start value first,
        // then fall back to the cheapest reachable successor for the selected city.
        Solver solver = model.getSolver();
        if (greedySucc != null) {
            for (int i = 0; i < N; i++) {
                solver.addHint(succ[i], greedySucc[i]);
            }
        }
        solver.setSearch(
            Search.intVarSearch(
                variables -> selectRewardVariable(variables, rewards),
                var -> selectSuccessorValue(var, succ, greedySucc, D, INF),
                succ)
        );
        solver.setGeometricalRestart(100, 1.5, new FailCounter(model, 100), 50);
        if (timeLimitSeconds > 0) {
            solver.limitTime(timeLimitSeconds + "s");
        }

        // --- Solve and collect best solution ---
        int[]  bestSucc      = greedySucc;
        int    bestReward    = greedyReward;
        int    bestCost      = greedyCost;

        while (solver.solve()) {
            int reward = totReward.getValue();
            int cost = totCost.getValue();
            if (reward > bestReward || (reward == bestReward && (bestCost < 0 || cost < bestCost))) {
                bestReward = reward;
                bestCost   = cost;
                bestSucc   = new int[N];
                for (int i = 0; i < N; i++) bestSucc[i] = succ[i].getValue();
            }
        }

        // --- Build output ---
        PrintWriter out = (outputFile != null)
            ? new PrintWriter(new FileWriter(outputFile))
            : new PrintWriter(new OutputStreamWriter(System.out));

        if (bestSucc == null) {
            out.println("No feasible solution found within budget.");
        } else {
            // Reconstruct tour path (1-indexed)
            List<Integer> tour = new ArrayList<>();
            int current = 0;
            tour.add(1); // depot, 1-indexed
            do {
                current = bestSucc[current];
                tour.add(current + 1); // convert back to 1-indexed
            } while (current != 0);

            // Line 1: reward and cost
            out.println(bestReward + " " + bestCost);

            // Line 2: tour sequence
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < tour.size(); i++) {
                if (i > 0) sb.append(" ");
                sb.append(tour.get(i));
            }
            out.println(sb);
        }

        out.flush();
        out.close();
    }

    private static void printUsage() {
        System.err.println("Usage: java -jar ttsp-choco.jar -i <input_file> -b <budget> [-o <output_file>] [-t <seconds>]");
        System.err.println("  -i  Path to input file (required)");
        System.err.println("  -b  Travel budget (required)");
        System.err.println("  -o  Path to output file (optional, defaults to stdout)");
        System.err.println("  -t  Search time limit in seconds (optional, defaults to 30; use 0 for no limit)");
    }

    private static IntVar selectRewardVariable(IntVar[] variables, int[] rewards) {
        IntVar best = null;
        int bestReward = -1;
        for (int i = 1; i < variables.length; i++) {
            if (!variables[i].isInstantiated() && rewards[i] > bestReward) {
                best = variables[i];
                bestReward = rewards[i];
            }
        }
        if (best != null) {
            return best;
        }
        for (IntVar variable : variables) {
            if (!variable.isInstantiated()) {
                return variable;
            }
        }
        return null;
    }

    private static int selectSuccessorValue(IntVar var, IntVar[] succ, int[] greedySucc, int[][] distances, int inf) {
        int i = indexOf(succ, var);
        if (i < 0) {
            return var.getLB();
        }
        if (greedySucc != null && var.contains(greedySucc[i])) {
            return greedySucc[i];
        }

        int best = var.contains(i) ? i : var.getLB();
        int minCost = inf;
        for (int j = 0; j < distances.length; j++) {
            if (j != i && var.contains(j) && distances[i][j] < minCost) {
                best = j;
                minCost = distances[i][j];
            }
        }
        return best;
    }

    private static int[] greedyWarmStart(int n, int[][] distances, int[] rewards, int budget, int inf) {
        int[] succ = new int[n];
        for (int i = 0; i < n; i++) {
            succ[i] = i;
        }

        boolean[] visited = new boolean[n];
        visited[0] = true;
        int current = 0;
        int remaining = budget;

        while (true) {
            int best = -1;
            double bestScore = -1.0;
            for (int j = 1; j < n; j++) {
                if (visited[j] || distances[current][j] >= inf || distances[j][0] >= inf) {
                    continue;
                }
                int requiredCost = distances[current][j] + distances[j][0];
                if (requiredCost > remaining) {
                    continue;
                }
                double score = (double) rewards[j] / distances[current][j];
                if (score > bestScore || (score == bestScore && rewards[j] > (best < 0 ? -1 : rewards[best]))) {
                    best = j;
                    bestScore = score;
                }
            }
            if (best < 0) {
                break;
            }
            succ[current] = best;
            remaining -= distances[current][best];
            visited[best] = true;
            current = best;
        }

        if (current == 0 || distances[current][0] > remaining) {
            return null;
        }
        succ[current] = 0;
        return succ;
    }

    private static int indexOf(IntVar[] variables, IntVar target) {
        for (int i = 0; i < variables.length; i++) {
            if (variables[i] == target) {
                return i;
            }
        }
        return -1;
    }

    private static int rewardOf(int[] succ, int[] rewards) {
        int reward = 0;
        for (int i = 1; i < succ.length; i++) {
            if (succ[i] != i) {
                reward += rewards[i];
            }
        }
        return reward;
    }

    private static int costOf(int[] succ, int[][] distances) {
        int cost = 0;
        for (int i = 0; i < succ.length; i++) {
            if (succ[i] != i) {
                cost += distances[i][succ[i]];
            }
        }
        return cost;
    }
}
