package com.lzke.ai.service;

import com.lzke.ai.adapter.BaseSystemAdapter;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
@RequiredArgsConstructor
public class TaskAggregatorService {

    private final List<BaseSystemAdapter> adapters;

    /**
     * 聚合多系统待办任务
     */
    public List<Map<String, Object>> aggregateTasks(String userId, String status, int page, int size) {
        List<Map<String, Object>> allTasks = new ArrayList<>();
        for (BaseSystemAdapter adapter : adapters) {
            try {
                allTasks.addAll(adapter.fetchTasks(userId));
            } catch (Exception e) {
                // 单个适配器失败不影响其他系统
                Map<String, Object> errorTask = new HashMap<>();
                errorTask.put("source", adapter.getSystemName());
                errorTask.put("error", e.getMessage());
                allTasks.add(errorTask);
            }
        }
        // TODO: 按优先级排序、分页
        return allTasks;
    }
}
