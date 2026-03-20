package com.lzke.ai.controller;

import com.lzke.ai.model.dto.TaskAggregateQuery;
import com.lzke.ai.model.vo.ApiResponse;
import com.lzke.ai.model.vo.TaskVO;
import com.lzke.ai.service.TaskAggregatorService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final TaskAggregatorService taskAggregatorService;

    @GetMapping("/aggregate")
    public ApiResponse<List<TaskVO>> aggregateTasks(TaskAggregateQuery query) {
        return ApiResponse.ok(taskAggregatorService.aggregateTasks(query));
    }
}
