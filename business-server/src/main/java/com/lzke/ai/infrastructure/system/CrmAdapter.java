package com.lzke.ai.infrastructure.system;

import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;
import java.util.Map;

@Component
public class CrmAdapter extends BaseSystemAdapter {

    @Override
    public String getSystemName() {
        return "crm";
    }

    @Override
    public List<Map<String, Object>> fetchTasks(String userId) {
        // TODO: 对接CRM系统API
        return Collections.emptyList();
    }

    @Override
    public Map<String, Object> executeAction(String action, Map<String, Object> params) {
        // TODO: 执行CRM操作
        return Map.of("status", "not_implemented");
    }
}
