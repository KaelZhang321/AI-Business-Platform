package com.lzke.ai.application.task;

import com.lzke.ai.application.dto.TaskAggregateQuery;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.interfaces.dto.TaskVO;
import com.lzke.ai.infrastructure.persistence.mapper.TaskMapper;
import com.lzke.ai.infrastructure.system.BaseSystemAdapter;
import lombok.RequiredArgsConstructor;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class TaskApplicationService {

    private final List<BaseSystemAdapter> adapters;
    private final TaskMapper taskMapper;

    /**
     * 聚合多系统待办任务
     */
    @Cacheable(cacheNames = "tasks", key = "#query.userId + ':' + #query.page + ':' + #query.size")
    public PageResult<TaskVO> aggregateTasks(TaskAggregateQuery query) {
        List<TaskVO> allTasks = new ArrayList<>();

        for (BaseSystemAdapter adapter : adapters) {
            try {
                List<Map<String, Object>> rawTasks = adapter.fetchTasks(query.getUserId());
                for (Map<String, Object> raw : rawTasks) {
                    TaskVO vo = new TaskVO();
                    vo.setSourceSystem(adapter.getSystemName());
                    vo.setSourceId(raw.get("sourceId") != null ? raw.get("sourceId").toString() : null);
                    vo.setTitle((String) raw.getOrDefault("title", ""));
                    vo.setDescription((String) raw.get("description"));
                    vo.setStatus((String) raw.getOrDefault("status", "pending"));
                    vo.setPriority((String) raw.getOrDefault("priority", "normal"));
                    vo.setDeadline(raw.get("deadline") != null ? raw.get("deadline").toString() : null);
                    vo.setExternalUrl((String) raw.get("externalUrl"));
                    allTasks.add(vo);
                }
            } catch (Exception e) {
                TaskVO errorVo = new TaskVO();
                errorVo.setSourceSystem(adapter.getSystemName());
                errorVo.setError(e.getMessage());
                allTasks.add(errorVo);
            }
        }

        // 按优先级排序：urgent > high > normal > low
        Map<String, Integer> priorityOrder = Map.of(
                "urgent", 0, "high", 1, "normal", 2, "low", 3
        );
        allTasks.sort(Comparator.comparingInt(t ->
                priorityOrder.getOrDefault(t.getPriority(), 99)));

        // 手动分页
        int page = Math.max(query.getPage(), 1);
        int size = Math.max(query.getSize(), 10);
        int fromIndex = (page - 1) * size;
        int toIndex = Math.min(fromIndex + size, allTasks.size());
        List<TaskVO> pagedTasks = fromIndex < allTasks.size()
                ? allTasks.subList(fromIndex, toIndex)
                : List.of();

        return PageResult.of(pagedTasks, allTasks.size(), page, size);
    }
}
