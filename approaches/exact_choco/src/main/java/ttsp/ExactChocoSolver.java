package ttsp;

import org.chocosolver.solver.Model;
import org.chocosolver.solver.variables.BoolVar;
import org.chocosolver.solver.variables.IntVar;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public final class ExactChocoSolver {
    private static final int DEPOT = 1;
    private static final int INF = 1_000_000_000;

    private ExactChocoSolver() {
    }

    public static void main(String[] args) throws IOException {
        Arguments arguments = Arguments.parse(args);
        Path inputPath = arguments.inputPath();
        Path outputPath = arguments.outputPath();
        Path metadataPath = arguments.metadataPath();

        if (Files.isDirectory(inputPath)) {
            if (outputPath == null) {
                throw new IllegalArgumentException("--output is required when --input is a directory.");
            }
            if (metadataPath != null && metadataPath.toString().endsWith(".json")) {
                throw new IllegalArgumentException("--metadata-output must be a directory when --input is a directory.");
            }
            Files.createDirectories(outputPath);
            if (metadataPath != null) {
                Files.createDirectories(metadataPath);
            }
            try (var stream = Files.list(inputPath)) {
                for (Path instancePath : stream
                        .filter(Files::isRegularFile)
                        .filter(path -> !path.getFileName().toString().startsWith("."))
                        .sorted()
                        .toList()) {
                    RunResult result = solveOne(instancePath, arguments.budget());
                    Files.writeString(outputPath.resolve(instancePath.getFileName()), result.solution().format());
                    if (metadataPath != null) {
                        String metadataName = stripExtension(instancePath.getFileName().toString()) + ".json";
                        Files.writeString(metadataPath.resolve(metadataName), result.metadataJson(instancePath));
                    }
                }
            }
        } else {
            RunResult result = solveOne(inputPath, arguments.budget());
            if (outputPath == null) {
                System.out.print(result.solution().format());
            } else {
                Path destination = Files.isDirectory(outputPath) ? outputPath.resolve(inputPath.getFileName()) : outputPath;
                if (destination.getParent() != null) {
                    Files.createDirectories(destination.getParent());
                }
                Files.writeString(destination, result.solution().format());
            }
            if (metadataPath != null) {
                Path destination = Files.isDirectory(metadataPath)
                        ? metadataPath.resolve(stripExtension(inputPath.getFileName().toString()) + ".json")
                        : metadataPath;
                if (destination.getParent() != null) {
                    Files.createDirectories(destination.getParent());
                }
                Files.writeString(destination, result.metadataJson(inputPath));
            }
        }
    }

    private static RunResult solveOne(Path inputPath, int budget) throws IOException {
        long startNanos = System.nanoTime();
        Instance instance = Instance.read(inputPath);
        ShortestPaths shortestPaths = ShortestPaths.from(instance.graph());
        Solution best = solve(instance, shortestPaths, budget);
        double runtimeSeconds = (System.nanoTime() - startNanos) / 1_000_000_000.0;
        return new RunResult(best, runtimeSeconds);
    }

    private static Solution solve(Instance instance, ShortestPaths shortestPaths, int budget) {
        Solution best = new Solution(0, 0, List.of(DEPOT));
        int maxVisits = instance.n() - 1;

        for (int visitCount = 1; visitCount <= maxVisits; visitCount++) {
            Solution candidate = solveWithVisitCount(instance, shortestPaths, budget, visitCount);
            if (candidate != null && isBetter(candidate, best)) {
                best = candidate;
            }
        }

        return best;
    }

    private static Solution solveWithVisitCount(
            Instance instance,
            ShortestPaths shortestPaths,
            int budget,
            int visitCount
    ) {
        int n = instance.n();
        int routeLength = visitCount + 2;
        Model model = new Model("ttsp-exact-k-" + visitCount);

        IntVar[] route = new IntVar[routeLength];
        route[0] = model.intVar("route_0", DEPOT);
        route[routeLength - 1] = model.intVar("route_" + (routeLength - 1), DEPOT);

        int[] nonDepotNodes = nonDepotNodes(n);
        for (int i = 1; i <= visitCount; i++) {
            route[i] = model.intVar("route_" + i, nonDepotNodes);
        }
        model.allDifferent(Arrays.copyOfRange(route, 1, routeLength - 1)).post();

        int pairTableSize = (n + 1) * (n + 1);
        int[] distanceTable = flatten(shortestPaths.distances(), n);
        IntVar[] segmentCosts = new IntVar[routeLength - 1];
        BoolVar[][] segmentVisits = new BoolVar[n + 1][routeLength - 1];

        for (int i = 0; i < routeLength - 1; i++) {
            IntVar pairIndex = model.intVar("pair_" + i, 0, pairTableSize - 1);
            model.scalar(new IntVar[]{route[i], route[i + 1]}, new int[]{n + 1, 1}, "=", pairIndex).post();

            segmentCosts[i] = model.intVar("cost_" + i, 0, INF);
            model.element(segmentCosts[i], distanceTable, pairIndex, 0).post();

            for (int node = 1; node <= n; node++) {
                segmentVisits[node][i] = model.boolVar("segment_" + i + "_visits_" + node);
                model.element(segmentVisits[node][i], shortestPaths.visitTableFor(node), pairIndex, 0).post();
            }
        }

        IntVar totalCost = model.intVar("total_cost", 0, INF);
        model.sum(segmentCosts, "=", totalCost).post();
        model.arithm(totalCost, "<=", budget).post();

        BoolVar[] visited = new BoolVar[n - 1];
        int[] rewards = new int[n - 1];
        int cursor = 0;
        for (int node = 1; node <= n; node++) {
            if (node == DEPOT) {
                continue;
            }
            visited[cursor] = model.boolVar("visited_" + node);
            model.max(visited[cursor], segmentVisits[node]).post();
            rewards[cursor] = instance.rewards()[node - 1];
            cursor++;
        }

        IntVar totalReward = model.intVar("total_reward", 0, Arrays.stream(instance.rewards()).sum());
        model.scalar(visited, rewards, "=", totalReward).post();
        model.setObjective(Model.MAXIMIZE, totalReward);

        int bestReward = -1;
        int bestCost = INF;
        int[] bestRoute = null;

        while (model.getSolver().solve()) {
            int reward = totalReward.getValue();
            int cost = totalCost.getValue();
            if (reward > bestReward || (reward == bestReward && cost < bestCost)) {
                bestReward = reward;
                bestCost = cost;
                bestRoute = Arrays.stream(route).mapToInt(IntVar::getValue).toArray();
            }
        }

        if (bestRoute == null) {
            return null;
        }

        List<Integer> walk = shortestPaths.expand(bestRoute);
        int validatedCost = walkCost(walk, instance.graph());
        int validatedReward = walkReward(walk, instance.rewards());
        return new Solution(validatedReward, validatedCost, walk);
    }

    private static boolean isBetter(Solution candidate, Solution incumbent) {
        if (candidate.reward() != incumbent.reward()) {
            return candidate.reward() > incumbent.reward();
        }
        return candidate.cost() < incumbent.cost();
    }

    private static int[] nonDepotNodes(int n) {
        int[] nodes = new int[n - 1];
        int cursor = 0;
        for (int node = 1; node <= n; node++) {
            if (node != DEPOT) {
                nodes[cursor++] = node;
            }
        }
        return nodes;
    }

    private static int[] flatten(int[][] matrix, int n) {
        int[] flattened = new int[(n + 1) * (n + 1)];
        for (int from = 0; from <= n; from++) {
            for (int to = 0; to <= n; to++) {
                flattened[from * (n + 1) + to] = matrix[from][to];
            }
        }
        return flattened;
    }

    private static int walkCost(List<Integer> walk, int[][] graph) {
        int cost = 0;
        for (int i = 0; i < walk.size() - 1; i++) {
            cost += graph[walk.get(i)][walk.get(i + 1)];
        }
        return cost;
    }

    private static int walkReward(List<Integer> walk, int[] rewards) {
        boolean[] visited = new boolean[rewards.length + 1];
        for (int node : walk) {
            visited[node] = true;
        }
        int reward = 0;
        for (int node = 1; node < visited.length; node++) {
            if (node != DEPOT && visited[node]) {
                reward += rewards[node - 1];
            }
        }
        return reward;
    }

    private static String join(List<Integer> values) {
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) {
                builder.append(' ');
            }
            builder.append(values.get(i));
        }
        return builder.toString();
    }

    private record Arguments(Path inputPath, Path outputPath, Path metadataPath, int budget) {
        static Arguments parse(String[] args) {
            Path inputPath = null;
            Path outputPath = null;
            Path metadataPath = null;
            Integer budget = null;

            for (int i = 0; i < args.length; i++) {
                switch (args[i]) {
                    case "--input", "-i" -> inputPath = Path.of(args[++i]);
                    case "--output", "-o" -> outputPath = Path.of(args[++i]);
                    case "--metadata-output" -> metadataPath = Path.of(args[++i]);
                    case "--budget", "-b" -> budget = Integer.parseInt(args[++i]);
                    default -> throw new IllegalArgumentException("Unknown argument: " + args[i]);
                }
            }

            if (inputPath == null) {
                throw new IllegalArgumentException("--input is required.");
            }
            if (budget == null) {
                throw new IllegalArgumentException("--budget is required.");
            }
            if (budget < 0) {
                throw new IllegalArgumentException("Budget must be non-negative.");
            }
            return new Arguments(inputPath, outputPath, metadataPath, budget);
        }
    }

    private record Instance(int n, int[] rewards, int[][] graph) {
        static Instance read(Path path) throws IOException {
            List<String> lines = Files.readAllLines(path).stream()
                    .map(String::trim)
                    .filter(line -> !line.isEmpty())
                    .filter(line -> !line.startsWith("#"))
                    .toList();
            if (lines.size() < 2) {
                throw new IllegalArgumentException("Input file must contain at least a header and reward line.");
            }

            if (lines.get(0).equals("TTSP_MATRIX")) {
                return readMatrix(path, lines);
            }

            String[] header = lines.get(0).split("\\s+");
            int n = Integer.parseInt(header[0]);
            int m = Integer.parseInt(header[1]);
            int[] rewards = Arrays.stream(lines.get(1).split("\\s+"))
                    .mapToInt(Integer::parseInt)
                    .toArray();
            if (rewards.length != n) {
                throw new IllegalArgumentException("Input declares " + n + " nodes but contains " + rewards.length + " rewards.");
            }
            if (lines.size() - 2 != m) {
                throw new IllegalArgumentException("Input declares " + m + " edges but contains " + (lines.size() - 2) + " edge rows.");
            }

            int[][] graph = new int[n + 1][n + 1];
            for (int[] row : graph) {
                Arrays.fill(row, INF);
            }
            for (int node = 1; node <= n; node++) {
                graph[node][node] = 0;
            }

            for (int i = 2; i < lines.size(); i++) {
                String[] edge = lines.get(i).split("\\s+");
                int u = Integer.parseInt(edge[0]);
                int v = Integer.parseInt(edge[1]);
                int w = Integer.parseInt(edge[2]);
                graph[u][v] = w;
                graph[v][u] = w;
            }
            return new Instance(n, rewards, graph);
        }

        private static Instance readMatrix(Path path, List<String> lines) {
            if (lines.size() < 3) {
                throw new IllegalArgumentException("Matrix input " + path + " must contain node count, rewards, and matrix rows.");
            }

            int n = Integer.parseInt(lines.get(1));
            int[] rewards = Arrays.stream(lines.get(2).split("\\s+"))
                    .mapToInt(Integer::parseInt)
                    .toArray();
            if (rewards.length != n) {
                throw new IllegalArgumentException("Input declares " + n + " nodes but contains " + rewards.length + " rewards.");
            }
            if (lines.size() - 3 != n) {
                throw new IllegalArgumentException("Matrix input declares " + n + " nodes but contains " + (lines.size() - 3) + " matrix rows.");
            }

            int[][] graph = new int[n + 1][n + 1];
            for (int row = 1; row <= n; row++) {
                int[] weights = Arrays.stream(lines.get(row + 2).split("\\s+"))
                        .mapToInt(Integer::parseInt)
                        .toArray();
                if (weights.length != n) {
                    throw new IllegalArgumentException("Matrix row " + row + " contains " + weights.length + " values, expected " + n + ".");
                }
                for (int column = 1; column <= n; column++) {
                    graph[row][column] = weights[column - 1];
                }
            }
            return new Instance(n, rewards, graph);
        }
    }

    private record Solution(int reward, int cost, List<Integer> walk) {
        String format() {
            return reward + " " + cost + "\n" + join(walk) + "\n";
        }
    }

    private record RunResult(Solution solution, double runtimeSeconds) {
        String metadataJson(Path inputPath) {
            int routeHops = Math.max(solution.walk().size() - 1, 0);
            return "{\n"
                    + "  \"input\": " + jsonString(inputPath.toString()) + ",\n"
                    + "  \"runtime_seconds\": " + String.format(java.util.Locale.ROOT, "%.9f", runtimeSeconds) + ",\n"
                    + "  \"reward\": " + solution.reward() + ",\n"
                    + "  \"cost\": " + solution.cost() + ",\n"
                    + "  \"route_hops\": " + routeHops + "\n"
                    + "}\n";
        }
    }

    private static String stripExtension(String name) {
        int index = name.lastIndexOf('.');
        return index < 0 ? name : name.substring(0, index);
    }

    private static String jsonString(String value) {
        return "\"" + value
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t")
                + "\"";
    }

    private static final class ShortestPaths {
        private final int[][] distances;
        private final int[][] next;
        private final int[][] visitTables;
        private final int n;

        private ShortestPaths(int[][] distances, int[][] next, int[][] visitTables, int n) {
            this.distances = distances;
            this.next = next;
            this.visitTables = visitTables;
            this.n = n;
        }

        static ShortestPaths from(int[][] graph) {
            int n = graph.length - 1;
            int[][] distances = new int[n + 1][n + 1];
            int[][] next = new int[n + 1][n + 1];

            for (int from = 1; from <= n; from++) {
                for (int to = 1; to <= n; to++) {
                    distances[from][to] = graph[from][to];
                    if (graph[from][to] < INF && from != to) {
                        next[from][to] = to;
                    }
                }
            }

            for (int through = 1; through <= n; through++) {
                for (int from = 1; from <= n; from++) {
                    for (int to = 1; to <= n; to++) {
                        if (distances[from][through] == INF || distances[through][to] == INF) {
                            continue;
                        }
                        int candidate = distances[from][through] + distances[through][to];
                        if (candidate < distances[from][to]) {
                            distances[from][to] = candidate;
                            next[from][to] = next[from][through];
                        }
                    }
                }
            }

            int[][] visitTables = new int[n + 1][(n + 1) * (n + 1)];
            for (int node = 1; node <= n; node++) {
                for (int from = 1; from <= n; from++) {
                    for (int to = 1; to <= n; to++) {
                        List<Integer> path = expandSegment(from, to, next);
                        visitTables[node][from * (n + 1) + to] = path.contains(node) ? 1 : 0;
                    }
                }
            }

            return new ShortestPaths(distances, next, visitTables, n);
        }

        int[][] distances() {
            return distances;
        }

        int[] visitTableFor(int node) {
            return visitTables[node];
        }

        List<Integer> expand(int[] route) {
            List<Integer> walk = new ArrayList<>();
            for (int i = 0; i < route.length - 1; i++) {
                List<Integer> segment = expandSegment(route[i], route[i + 1], next);
                if (i > 0 && !segment.isEmpty()) {
                    segment = segment.subList(1, segment.size());
                }
                walk.addAll(segment);
            }
            return walk;
        }

        private static List<Integer> expandSegment(int from, int to, int[][] next) {
            if (from == to) {
                return List.of(from);
            }
            if (next[from][to] == 0) {
                return List.of();
            }

            List<Integer> path = new ArrayList<>();
            int current = from;
            path.add(current);
            while (current != to) {
                current = next[current][to];
                path.add(current);
            }
            return path;
        }
    }
}
