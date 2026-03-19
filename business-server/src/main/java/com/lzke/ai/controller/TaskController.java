package com.lzke.ai.controller;

import com.lzke.ai.service.TaskAggregatorService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final TaskAggregatorService taskAggregatorService;

    @GetMapping("/aggregate")
    public ResponseEntity<List<Map<String, Object>>> aggregateTasks(
            @RequestParam(required = false) String userId,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(taskAggregatorService.aggregateTasks(userId, status, page, size));
    }
}
