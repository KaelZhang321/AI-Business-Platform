package com.lzke.ai.adapter;

import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;
import java.util.Map;

@Component
public class OaAdapter extends BaseSystemAdapter {

    @Override
    public String getSystemName() {
        return "oa";
    }

    @Override
    public List<Map<String, Object>> fetchTasks(String userId) {
        // TODO: 对接OA系统API
        return Collections.emptyList();
    }

    @Override
    public Map<String, Object> executeAction(String action, Map<String, Object> params) {
        // TODO: 执行OA操作
        return Map.of("status", "not_implemented");
    }
}
