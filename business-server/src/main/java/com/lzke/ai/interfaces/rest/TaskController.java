package com.lzke.ai.interfaces.rest;

import com.lzke.ai.application.dto.TaskAggregateQuery;
import com.lzke.ai.application.task.TaskApplicationService;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.interfaces.dto.TaskVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final TaskApplicationService taskApplicationService;

    @GetMapping("/aggregate")
    public ApiResponse<PageResult<TaskVO>> aggregateTasks(TaskAggregateQuery query) {
        return ApiResponse.ok(taskApplicationService.aggregateTasks(query));
    }
}
