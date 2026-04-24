package com.lzke.ai.application.rule;

import java.util.HashMap;
import java.util.Map;

public abstract class RuleNode {
    
    private String nodeId;
    private Integer nodeGroup;
    private Map<String, Object> context;

    public RuleNode(String nodeId) {
        this(nodeId, 0);
    }

    public RuleNode(String nodeId, Integer nodeGroup) {
        this.nodeId = nodeId;
        this.nodeGroup = nodeGroup;
        this.context = new HashMap<>();
    }

    public String getNodeId() {
        return nodeId;
    }

    public Integer getNodeGroup() {
        return nodeGroup;
    }

    public void setNodeGroup(Integer nodeGroup) {
        this.nodeGroup = nodeGroup;
    }

    public Map<String, Object> getContext() {
        return context;
    }

    public void setContext(Map<String, Object> context) {
        this.context = context;
    }

    public abstract Map<String, Object> execute(Map<String, Object> input) throws Exception;
}
