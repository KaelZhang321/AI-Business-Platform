package com.lzke.ai.application.task;

import com.lzke.ai.application.dto.TaskAggregateQuery;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.interfaces.dto.TaskVO;
import com.lzke.ai.infrastructure.persistence.mapper.TaskMapper;
import com.lzke.ai.infrastructure.system.BaseSystemAdapter;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
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
    public PageResult<TaskVO> aggregateTasks(TaskAggregateQuery query) {
        List<TaskVO> allTasks = new ArrayList<>();

        for (BaseSystemAdapter adapter : adapters) {
            try {
                List<Map<String, Object>> rawTasks = adapter.fetchTasks(query.getUserId());
                for (Map<String, Object> raw : rawTasks) {
                    TaskVO vo = new TaskVO();
                    vo.setSourceSystem(adapter.getSystemName());
                    vo.setTitle((String) raw.getOrDefault("title", ""));
                    vo.setStatus((String) raw.getOrDefault("status", "pending"));
                    vo.setPriority((String) raw.getOrDefault("priority", "normal"));
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

        // TODO: 按优先级排序、分页
        return PageResult.of(allTasks, allTasks.size(), query.getPage(), query.getSize());
    }
}
