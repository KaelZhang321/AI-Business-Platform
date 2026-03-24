package com.lzke.ai.interfaces.rest;

import com.lzke.ai.annotation.RateLimit;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.service.WorkflowService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 工作流控制器 — 流程部署/启动/审批/查询。
 */
@RestController
@RequestMapping("/api/v1/workflow")
@RequiredArgsConstructor
public class WorkflowController {

    private final WorkflowService workflowService;

    /**
     * 部署流程定义
     */
    @PostMapping("/deploy")
    @RateLimit(permits = 10, period = 60)
    public ApiResponse<Map<String, Object>> deploy(@RequestParam String resourceName) {
        return ApiResponse.ok(workflowService.deployProcess(resourceName));
    }

    /**
     * 查询已部署的流程定义
     */
    @GetMapping("/definitions")
    public ApiResponse<List<Map<String, Object>>> listDefinitions() {
        return ApiResponse.ok(workflowService.listProcessDefinitions());
    }

    /**
     * 启动流程实例
     */
    @PostMapping("/start")
    @RateLimit(permits = 50, period = 60)
    public ApiResponse<Map<String, Object>> startProcess(
            @RequestParam String processDefinitionKey,
            @RequestParam String initiatorId,
            @RequestBody(required = false) Map<String, Object> variables) {
        return ApiResponse.ok(workflowService.startProcess(processDefinitionKey, initiatorId, variables));
    }

    /**
     * 查询用户待办任务
     */
    @GetMapping("/tasks")
    public ApiResponse<List<Map<String, Object>>> listUserTasks(@RequestParam String assignee) {
        return ApiResponse.ok(workflowService.listUserTasks(assignee));
    }

    /**
     * 查询候选组待办任务
     */
    @GetMapping("/tasks/candidate")
    public ApiResponse<List<Map<String, Object>>> listCandidateTasks(@RequestParam String candidateGroup) {
        return ApiResponse.ok(workflowService.listCandidateTasks(candidateGroup));
    }

    /**
     * 完成任务（审批）
     */
    @PostMapping("/tasks/{taskId}/complete")
    public ApiResponse<Void> completeTask(
            @PathVariable String taskId,
            @RequestBody(required = false) Map<String, Object> variables) {
        workflowService.completeTask(taskId, variables);
        return ApiResponse.ok(null);
    }

    /**
     * 认领任务
     */
    @PostMapping("/tasks/{taskId}/claim")
    public ApiResponse<Void> claimTask(
            @PathVariable String taskId,
            @RequestParam String userId) {
        workflowService.claimTask(taskId, userId);
        return ApiResponse.ok(null);
    }
}
