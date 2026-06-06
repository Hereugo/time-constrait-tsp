package ttsp;

import com.graphhopper.jsprit.core.algorithm.VehicleRoutingAlgorithm;
import com.graphhopper.jsprit.core.algorithm.box.Jsprit;
import com.graphhopper.jsprit.core.problem.Location;
import com.graphhopper.jsprit.core.problem.VehicleRoutingProblem;
import com.graphhopper.jsprit.core.problem.cost.VehicleRoutingTransportCosts;
import com.graphhopper.jsprit.core.problem.driver.Driver;
import com.graphhopper.jsprit.core.problem.job.Job;
import com.graphhopper.jsprit.core.problem.job.Service;
import com.graphhopper.jsprit.core.problem.solution.SolutionCostCalculator;
import com.graphhopper.jsprit.core.problem.solution.VehicleRoutingProblemSolution;
import com.graphhopper.jsprit.core.problem.solution.route.VehicleRoute;
import com.graphhopper.jsprit.core.problem.solution.route.activity.TourActivity;
import com.graphhopper.jsprit.core.problem.vehicle.Vehicle;
import com.graphhopper.jsprit.core.problem.vehicle.VehicleImpl;
import com.graphhopper.jsprit.core.problem.vehicle.VehicleType;
import com.graphhopper.jsprit.core.problem.vehicle.VehicleTypeImpl;
import com.graphhopper.jsprit.core.util.RandomNumberGeneration;
import com.graphhopper.jsprit.core.util.Solutions;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import java.util.Random;
import java.util.Set;

public final class JspritHeuristic {
    private static final int DEPOT = 1;
    private static final int INF = 1_000_000_000;

    private JspritHeuristic() {
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
                    Solution solution = solveOne(instancePath, arguments);
                    Files.writeString(outputPath.resolve(instancePath.getFileName()), solution.format());
                    if (metadataPath != null) {
                        String metadataName = stripExtension(instancePath.getFileName().toString()) + ".json";
                        Files.writeString(metadataPath.resolve(metadataName), solution.metadataJson());
                    }
                }
            }
        } else {
            Solution solution = solveOne(inputPath, arguments);
            if (outputPath == null) {
                System.out.print(solution.format());
            } else {
                Path destination = Files.isDirectory(outputPath) ? outputPath.resolve(inputPath.getFileName()) : outputPath;
                if (destination.getParent() != null) {
                    Files.createDirectories(destination.getParent());
                }
                Files.writeString(destination, solution.format());
            }
            if (metadataPath != null) {
                Path destination = Files.isDirectory(metadataPath)
                        ? metadataPath.resolve(stripExtension(inputPath.getFileName().toString()) + ".json")
                        : metadataPath;
                if (destination.getParent() != null) {
                    Files.createDirectories(destination.getParent());
                }
                Files.writeString(destination, solution.metadataJson());
            }
        }
    }

    private static Solution solveOne(Path instancePath, Arguments arguments) throws IOException {
        long startNanos = System.nanoTime();
        Instance instance = Instance.read(instancePath);
        ShortestPaths shortestPaths = ShortestPaths.from(instance);

        List<Integer> reachableServices = new ArrayList<>();
        List<Integer> unreachableServices = new ArrayList<>();
        int totalExplicitReward = 0;
        for (int node = 1; node <= instance.n(); node++) {
            if (node == DEPOT || instance.rewards()[node - 1] <= 0) {
                continue;
            }
            if (shortestPaths.distances()[DEPOT][node] >= INF) {
                unreachableServices.add(node);
            } else {
                reachableServices.add(node);
                totalExplicitReward += instance.rewards()[node - 1];
            }
        }

        List<Integer> selectedServices = List.of();
        if (!reachableServices.isEmpty()) {
            selectedServices = runJsprit(instance, shortestPaths, reachableServices, totalExplicitReward, arguments);
        }

        List<Integer> selectedTour = new ArrayList<>();
        selectedTour.add(DEPOT);
        selectedTour.addAll(selectedServices);
        selectedTour.add(DEPOT);

        List<Integer> walk = shortestPaths.expand(selectedTour);
        int cost = walkCost(walk, instance.graph());
        int validatedReward = walkReward(walk, instance.rewards());
        int explicitReward = selectedServices.stream().mapToInt(node -> instance.rewards()[node - 1]).sum();
        if (cost > arguments.budget()) {
            throw new IllegalStateException("Jsprit returned an over-budget tour for " + instancePath + ": " + cost);
        }

        double runtimeSeconds = (System.nanoTime() - startNanos) / 1_000_000_000.0;
        Metadata metadata = new Metadata(
                arguments.seed(),
                arguments.iterations(),
                runtimeSeconds,
                explicitReward,
                validatedReward,
                cost,
                selectedServices,
                Math.max(walk.size() - 1, 0),
                reachableServices.size() - selectedServices.size(),
                unreachableServices
        );
        return new Solution(validatedReward, cost, walk, metadata);
    }

    private static List<Integer> runJsprit(
            Instance instance,
            ShortestPaths shortestPaths,
            List<Integer> serviceNodes,
            int totalExplicitReward,
            Arguments arguments
    ) {
        RandomNumberGeneration.setSeed(arguments.seed());
        Location depotLocation = Location.newInstance(String.valueOf(DEPOT));
        VehicleType vehicleType = VehicleTypeImpl.Builder.newInstance("ttsp-vehicle-type").build();
        VehicleImpl vehicle = VehicleImpl.Builder.newInstance("ttsp-vehicle")
                .setType(vehicleType)
                .setStartLocation(depotLocation)
                .setEndLocation(depotLocation)
                .setReturnToDepot(true)
                .setLatestArrival(arguments.budget())
                .build();

        VehicleRoutingProblem.Builder builder = VehicleRoutingProblem.Builder.newInstance()
                .setFleetSize(VehicleRoutingProblem.FleetSize.FINITE)
                .setRoutingCost(new ShortestPathTransportCosts(shortestPaths.distances()))
                .addVehicle(vehicle);

        for (int node : serviceNodes) {
            Service service = Service.Builder.newInstance(String.valueOf(node))
                    .setLocation(Location.newInstance(String.valueOf(node)))
                    .setServiceTime(0.0)
                    .setUserData(node)
                    .build();
            builder.addJob(service);
        }

        VehicleRoutingProblem problem = builder.build();
        SolutionCostCalculator objective = new ExplicitRewardObjective(
                instance.rewards(),
                shortestPaths.distances(),
                totalExplicitReward,
                arguments.budget()
        );
        VehicleRoutingAlgorithm algorithm = Jsprit.Builder.newInstance(problem)
                .setRandom(new Random(arguments.seed()))
                .setObjectiveFunction(objective)
                .buildAlgorithm();
        algorithm.setMaxIterations(arguments.iterations());

        Collection<VehicleRoutingProblemSolution> solutions = algorithm.searchSolutions();
        VehicleRoutingProblemSolution best = Solutions.bestOf(solutions);
        if (best == null || best.getRoutes().isEmpty()) {
            return List.of();
        }

        List<Integer> selected = new ArrayList<>();
        for (VehicleRoute route : best.getRoutes()) {
            for (TourActivity activity : route.getActivities()) {
                if (activity instanceof TourActivity.JobActivity jobActivity) {
                    selected.add(Integer.parseInt(jobActivity.getJob().getId()));
                }
            }
        }
        return selected;
    }

    private static int walkCost(List<Integer> walk, int[][] graph) {
        int cost = 0;
        for (int i = 0; i < walk.size() - 1; i++) {
            int edgeCost = graph[walk.get(i)][walk.get(i + 1)];
            if (edgeCost >= INF) {
                throw new IllegalStateException("Expanded walk contains a missing edge: " + walk.get(i) + "-" + walk.get(i + 1));
            }
            cost += edgeCost;
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

    private static String stripExtension(String name) {
        int index = name.lastIndexOf('.');
        return index < 0 ? name : name.substring(0, index);
    }

    private record Arguments(Path inputPath, Path outputPath, Path metadataPath, int budget, long seed, int iterations) {
        static Arguments parse(String[] args) {
            Path inputPath = null;
            Path outputPath = null;
            Path metadataPath = null;
            Integer budget = null;
            long seed = 1;
            int iterations = 2_000;

            for (int i = 0; i < args.length; i++) {
                switch (args[i]) {
                    case "--input" -> inputPath = Path.of(args[++i]);
                    case "--output" -> outputPath = Path.of(args[++i]);
                    case "--metadata-output" -> metadataPath = Path.of(args[++i]);
                    case "--budget" -> budget = Integer.parseInt(args[++i]);
                    case "--seed" -> seed = Long.parseLong(args[++i]);
                    case "--iterations" -> iterations = Integer.parseInt(args[++i]);
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
            if (iterations < 0) {
                throw new IllegalArgumentException("Iterations must be non-negative.");
            }
            return new Arguments(inputPath, outputPath, metadataPath, budget, seed, iterations);
        }
    }

    private record Instance(int n, int[] rewards, int[][] graph, List<List<Edge>> adjacency) {
        static Instance read(Path path) throws IOException {
            List<String> lines = Files.readAllLines(path).stream()
                    .map(String::trim)
                    .filter(line -> !line.isEmpty())
                    .toList();
            if (lines.size() < 2) {
                throw new IllegalArgumentException("Input file must contain at least a header and reward line.");
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
            List<List<Edge>> adjacency = new ArrayList<>();
            for (int node = 0; node <= n; node++) {
                adjacency.add(new ArrayList<>());
            }
            for (int i = 2; i < lines.size(); i++) {
                String[] edge = lines.get(i).split("\\s+");
                int u = Integer.parseInt(edge[0]);
                int v = Integer.parseInt(edge[1]);
                int w = Integer.parseInt(edge[2]);
                graph[u][v] = w;
                graph[v][u] = w;
                adjacency.get(u).add(new Edge(v, w));
                adjacency.get(v).add(new Edge(u, w));
            }
            return new Instance(n, rewards, graph, adjacency);
        }
    }

    private record Edge(int target, int weight) {
    }

    private record ShortestPaths(int[][] distances, int[][] predecessors) {
        static ShortestPaths from(Instance instance) {
            int n = instance.n();
            int[][] distances = new int[n + 1][n + 1];
            int[][] predecessors = new int[n + 1][n + 1];
            for (int source = 1; source <= n; source++) {
                dijkstra(source, instance.adjacency(), distances[source], predecessors[source]);
            }
            return new ShortestPaths(distances, predecessors);
        }

        private static void dijkstra(int source, List<List<Edge>> adjacency, int[] distances, int[] predecessors) {
            Arrays.fill(distances, INF);
            Arrays.fill(predecessors, 0);
            distances[source] = 0;
            PriorityQueue<int[]> queue = new PriorityQueue<>(Comparator.comparingInt(item -> item[0]));
            queue.add(new int[]{0, source});

            while (!queue.isEmpty()) {
                int[] item = queue.poll();
                int distance = item[0];
                int node = item[1];
                if (distance != distances[node]) {
                    continue;
                }
                for (Edge edge : adjacency.get(node)) {
                    int neighbor = edge.target();
                    int weight = edge.weight();
                    int nextDistance = distance + weight;
                    if (nextDistance < distances[neighbor]) {
                        distances[neighbor] = nextDistance;
                        predecessors[neighbor] = node;
                        queue.add(new int[]{nextDistance, neighbor});
                    }
                }
            }
        }

        List<Integer> expand(List<Integer> tour) {
            List<Integer> walk = new ArrayList<>();
            for (int i = 0; i < tour.size() - 1; i++) {
                List<Integer> segment = path(tour.get(i), tour.get(i + 1));
                if (i > 0 && !segment.isEmpty()) {
                    segment = segment.subList(1, segment.size());
                }
                walk.addAll(segment);
            }
            return walk;
        }

        private List<Integer> path(int source, int target) {
            if (distances[source][target] >= INF) {
                throw new IllegalStateException("No shortest path exists between " + source + " and " + target + ".");
            }
            List<Integer> reversed = new ArrayList<>();
            int current = target;
            reversed.add(current);
            while (current != source) {
                current = predecessors[source][current];
                if (current == 0) {
                    throw new IllegalStateException("Missing predecessor while expanding " + source + " to " + target + ".");
                }
                reversed.add(current);
            }
            List<Integer> path = new ArrayList<>();
            for (int i = reversed.size() - 1; i >= 0; i--) {
                path.add(reversed.get(i));
            }
            return path;
        }
    }

    private record Solution(int reward, int cost, List<Integer> walk, Metadata metadata) {
        String format() {
            return reward + " " + cost + "\n" + join(walk) + "\n";
        }

        String metadataJson() {
            return metadata.toJson();
        }
    }

    private record Metadata(
            long seed,
            int iterations,
            double runtimeSeconds,
            int explicitReward,
            int validatedReward,
            int cost,
            List<Integer> selectedServices,
            int expandedWalkHops,
            int unassignedServices,
            List<Integer> unreachableServices
    ) {
        String toJson() {
            return "{\n"
                    + "  \"seed\": " + seed + ",\n"
                    + "  \"iterations\": " + iterations + ",\n"
                    + "  \"runtime_seconds\": " + String.format(java.util.Locale.ROOT, "%.6f", runtimeSeconds) + ",\n"
                    + "  \"explicit_reward\": " + explicitReward + ",\n"
                    + "  \"validated_reward\": " + validatedReward + ",\n"
                    + "  \"cost\": " + cost + ",\n"
                    + "  \"selected_services\": " + selectedServices + ",\n"
                    + "  \"expanded_walk_hops\": " + expandedWalkHops + ",\n"
                    + "  \"unassigned_services\": " + unassignedServices + ",\n"
                    + "  \"unreachable_services\": " + unreachableServices + "\n"
                    + "}\n";
        }
    }

    private static final class ShortestPathTransportCosts implements VehicleRoutingTransportCosts {
        private final int[][] distances;

        private ShortestPathTransportCosts(int[][] distances) {
            this.distances = distances;
        }

        @Override
        public double getTransportCost(Location from, Location to, double departureTime, Driver driver, Vehicle vehicle) {
            return distance(from, to);
        }

        @Override
        public double getBackwardTransportCost(Location from, Location to, double arrivalTime, Driver driver, Vehicle vehicle) {
            return distance(from, to);
        }

        @Override
        public double getTransportTime(Location from, Location to, double departureTime, Driver driver, Vehicle vehicle) {
            return distance(from, to);
        }

        @Override
        public double getBackwardTransportTime(Location from, Location to, double arrivalTime, Driver driver, Vehicle vehicle) {
            return distance(from, to);
        }

        @Override
        public double getDistance(Location from, Location to, double departureTime, Vehicle vehicle) {
            return distance(from, to);
        }

        private double distance(Location from, Location to) {
            int source = Integer.parseInt(from.getId());
            int target = Integer.parseInt(to.getId());
            return distances[source][target];
        }
    }

    private static final class ExplicitRewardObjective implements SolutionCostCalculator {
        private final int[] rewards;
        private final int[][] distances;
        private final int totalExplicitReward;
        private final int budget;

        private ExplicitRewardObjective(int[] rewards, int[][] distances, int totalExplicitReward, int budget) {
            this.rewards = rewards;
            this.distances = distances;
            this.totalExplicitReward = totalExplicitReward;
            this.budget = budget;
        }

        @Override
        public double getCosts(VehicleRoutingProblemSolution solution) {
            int selectedReward = explicitReward(solution);
            int routeCost = routeCost(solution);
            double objective = (double) (totalExplicitReward - selectedReward) * (budget + 1L) + routeCost;
            if (routeCost > budget) {
                objective += 1_000_000_000.0 + routeCost;
            }
            return objective;
        }

        @Override
        public Map<String, Double> getCostBreakdown(VehicleRoutingProblemSolution solution) {
            Map<String, Double> breakdown = new HashMap<>();
            breakdown.put("explicit_reward", (double) explicitReward(solution));
            breakdown.put("route_cost", (double) routeCost(solution));
            return breakdown;
        }

        private int explicitReward(VehicleRoutingProblemSolution solution) {
            Set<Integer> visited = new HashSet<>();
            for (VehicleRoute route : solution.getRoutes()) {
                for (TourActivity activity : route.getActivities()) {
                    if (activity instanceof TourActivity.JobActivity jobActivity) {
                        Job job = jobActivity.getJob();
                        visited.add(Integer.parseInt(job.getId()));
                    }
                }
            }
            int reward = 0;
            for (int node : visited) {
                if (node != DEPOT) {
                    reward += rewards[node - 1];
                }
            }
            return reward;
        }

        private int routeCost(VehicleRoutingProblemSolution solution) {
            int cost = 0;
            for (VehicleRoute route : solution.getRoutes()) {
                int previous = DEPOT;
                for (TourActivity activity : route.getActivities()) {
                    if (activity instanceof TourActivity.JobActivity jobActivity) {
                        int node = Integer.parseInt(jobActivity.getJob().getId());
                        cost += distances[previous][node];
                        previous = node;
                    }
                }
                cost += distances[previous][DEPOT];
            }
            return cost;
        }
    }
}
