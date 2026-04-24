package com.lzke.ai.application.rule;

import java.util.*;

public class AggregateNode extends RuleNode {

    private List<String> includeKeys;
    private Map<String, String> keyMapping;

    public AggregateNode(String nodeId, List<String> includeKeys) {
        super(nodeId);
        this.includeKeys = includeKeys;
        this.keyMapping = new HashMap<>();
    }

    public AggregateNode(String nodeId, Map<String, String> keyMapping) {
        super(nodeId);
        this.keyMapping = keyMapping;
        this.includeKeys = new ArrayList<>(keyMapping.keySet());
    }

    public AggregateNode(String nodeId, Integer nodeGroup, List<String> includeKeys) {
        super(nodeId, nodeGroup);
        this.includeKeys = includeKeys;
        this.keyMapping = new HashMap<>();
    }

    public AggregateNode(String nodeId, Integer nodeGroup, Map<String, String> keyMapping) {
        super(nodeId, nodeGroup);
        this.keyMapping = keyMapping;
        this.includeKeys = new ArrayList<>(keyMapping.keySet());
    }

    @Override
    public Map<String, Object> execute(Map<String, Object> input) throws Exception {
        Map<String, Object> output = new HashMap<>();

        if (keyMapping != null && !keyMapping.isEmpty()) {
            for (Map.Entry<String, String> entry : keyMapping.entrySet()) {
                String sourceKey = entry.getKey();
                String targetKey = entry.getValue();
                if (input.containsKey(sourceKey)) {
                    output.put(targetKey, input.get(sourceKey));
                }
            }
        } else if (includeKeys != null && !includeKeys.isEmpty()) {
            for (String key : includeKeys) {
                if (input.containsKey(key)) {
                    output.put(key, input.get(key));
                }
            }
        } else {
            output.putAll(input);
        }

        return output;
    }
}
