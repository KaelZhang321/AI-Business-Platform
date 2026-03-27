package com.lzke.ai.interfaces.rest;

import com.lzke.ai.annotation.RateLimit;
import com.lzke.ai.application.dto.TaskAggregateQuery;
import com.lzke.ai.application.task.TaskApplicationService;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.interfaces.dto.TaskVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@Tag(name = "待办任务", description = "多系统待办聚合")
@RestController
@RequestMapping("/api/v1/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final TaskApplicationService taskApplicationService;

    @Operation(summary = "聚合查询待办任务", description = "从 ERP/CRM/OA/预约/业务中台/360 等系统聚合待办")
    @GetMapping("/aggregate")
    @RateLimit(permits = 100, period = 60)
    public ApiResponse<PageResult<TaskVO>> aggregateTasks(@Valid TaskAggregateQuery query) {
        return ApiResponse.ok(taskApplicationService.aggregateTasks(query));
    }
}
