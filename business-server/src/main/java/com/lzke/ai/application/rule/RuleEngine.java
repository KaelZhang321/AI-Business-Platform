package com.lzke.ai.application.rule;


import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

public class RuleEngine {

    private List<RuleNode> nodes;
    private String engineName;
    private ExecutorService taskExecutor;

    public RuleEngine(String engineName) {
        this.engineName = engineName;
        this.nodes = new ArrayList<>();
        this.taskExecutor = null;
    }

    public RuleEngine(String engineName, ExecutorService taskExecutor) {
        this.engineName = engineName;
        this.nodes = new ArrayList<>();
        this.taskExecutor = taskExecutor;
    }

    public RuleEngine addNode(RuleNode node) {
        this.nodes.add(node);
        return this;
    }

    public Map<String, Object> execute(Map<String, Object> initialInput) throws Exception {
        if (taskExecutor == null) {
            return executeSequential(initialInput);
        } else {
            return executeParallel(initialInput);
        }
    }

    private Map<String, Object> executeSequential(Map<String, Object> initialInput) throws Exception {
        Map<String, Object> context = new HashMap<>(initialInput);

        for (RuleNode node : nodes) {
            context = node.execute(context);
        }

        return context;
    }

    private Map<String, Object> executeParallel(Map<String, Object> initialInput) throws Exception {
        Map<String, Object> context = new HashMap<>(initialInput);

        Map<Integer, List<RuleNode>> groupedNodes = nodes.stream()
                .collect(Collectors.groupingBy(RuleNode::getNodeGroup, TreeMap::new, Collectors.toList()));

        for (Map.Entry<Integer, List<RuleNode>> entry : groupedNodes.entrySet()) {
            List<RuleNode> groupNodes = entry.getValue();

            if (groupNodes.size() == 1) {
                context = groupNodes.get(0).execute(context);
            } else {
                Map<String, Object> finalContext = new HashMap<>(context);
                List<Future<Map<String, Object>>> futures = new ArrayList<>();

                for (RuleNode node : groupNodes) {
                    Future<Map<String, Object>> future = taskExecutor.submit(() -> {
                        try {
                            return node.execute(finalContext);
                        } catch (Exception e) {
                            throw new RuntimeException("Node execution failed: " + node.getNodeId(), e);
                        }
                    });
                    futures.add(future);
                }

                Map<String, Object> mergedContext = new HashMap<>(finalContext);
                for (Future<Map<String, Object>> future : futures) {
                    try {
                        Map<String, Object> result = future.get();
                        mergedContext.putAll(result);
                    } catch (InterruptedException | ExecutionException e) {
                        throw new Exception("Failed to execute parallel nodes in group: " + entry.getKey(), e);
                    }
                }

                context = mergedContext;
            }
        }

        return context;
    }

    public String getEngineName() {
        return engineName;
    }

    public List<RuleNode> getNodes() {
        return nodes;
    }

    public ExecutorService getTaskExecutor() {
        return taskExecutor;
    }
}
