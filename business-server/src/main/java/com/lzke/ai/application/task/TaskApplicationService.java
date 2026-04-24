package com.lzke.ai.application.task;

import com.lzke.ai.application.dto.TaskAggregateQuery;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.interfaces.dto.TaskVO;
import com.lzke.ai.infrastructure.persistence.mapper.TaskMapper;
import com.lzke.ai.infrastructure.system.BaseSystemAdapter;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
@RequiredArgsConstructor
public class TaskApplicationService {

    private final List<BaseSystemAdapter> adapters;
    private final TaskMapper taskMapper;

    private static final long ADAPTER_TIMEOUT_SECONDS = 10;

    /**
     * 聚合多系统待办任务（并行调用适配器）
     */
    @Cacheable(cacheNames = "tasks", key = "#query.userId + ':' + #query.page + ':' + #query.size")
    public PageResult<TaskVO> aggregateTasks(TaskAggregateQuery query) {

        // 并行调用所有适配器
        List<CompletableFuture<List<TaskVO>>> futures = adapters.stream()
                .map(adapter -> CompletableFuture.supplyAsync(() -> fetchFromAdapter(adapter, query.getUserId()))
                        .orTimeout(ADAPTER_TIMEOUT_SECONDS, TimeUnit.SECONDS)
                        .exceptionally(ex -> {
                            log.warn("适配器 {} 调用失败: {}", adapter.getSystemName(), ex.getMessage());
                            TaskVO errorVo = new TaskVO();
                            errorVo.setSourceSystem(adapter.getSystemName());
                            errorVo.setError(ex.getMessage());
                            return List.of(errorVo);
                        }))
                .toList();

        // 等待所有适配器完成并汇总结果
        List<TaskVO> allTasks = futures.stream()
                .map(CompletableFuture::join)
                .flatMap(List::stream)
                .collect(ArrayList::new, ArrayList::add, ArrayList::addAll);

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

    private List<TaskVO> fetchFromAdapter(BaseSystemAdapter adapter, String userId) {
        List<TaskVO> result = new ArrayList<>();
        List<Map<String, Object>> rawTasks = adapter.fetchTasks(userId);
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
            result.add(vo);
        }
        return result;
    }
}
