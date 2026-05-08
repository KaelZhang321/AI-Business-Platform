//package com.lzke.ai.service;
//
//import lombok.RequiredArgsConstructor;
//import lombok.extern.slf4j.Slf4j;
//import org.flowable.engine.RepositoryService;
//import org.flowable.engine.RuntimeService;
//import org.flowable.engine.TaskService;
//import org.flowable.engine.repository.Deployment;
//import org.flowable.engine.repository.ProcessDefinition;
//import org.flowable.engine.runtime.ProcessInstance;
//import org.flowable.task.api.Task;
//import org.springframework.stereotype.Service;
//
//import java.util.HashMap;
//import java.util.List;
//import java.util.Map;
//import java.util.stream.Collectors;
//
///**
// * 工作流服务 — 封装 Flowable 流程引擎操作。
// */
//@Slf4j
//@Service
//@RequiredArgsConstructor
//public class WorkflowService {
//
//    private final RepositoryService repositoryService;
//    private final RuntimeService runtimeService;
//    private final TaskService taskService;
//
//    /**
//     * 部署流程定义（从 classpath 加载 BPMN 文件）
//     */
//    public Map<String, Object> deployProcess(String resourceName) {
//        Deployment deployment = repositoryService.createDeployment()
//                .addClasspathResource("processes/" + resourceName)
//                .name(resourceName.replace(".bpmn20.xml", ""))
//                .deploy();
//
//        Map<String, Object> result = new HashMap<>();
//        result.put("deploymentId", deployment.getId());
//        result.put("name", deployment.getName());
//        result.put("deployTime", deployment.getDeploymentTime());
//        log.info("流程部署成功: deploymentId={}, name={}", deployment.getId(), deployment.getName());
//        return result;
//    }
//
//    /**
//     * 查询已部署的流程定义列表
//     */
//    public List<Map<String, Object>> listProcessDefinitions() {
//        return repositoryService.createProcessDefinitionQuery()
//                .orderByProcessDefinitionVersion().desc()
//                .list()
//                .stream()
//                .map(this::toDefinitionMap)
//                .collect(Collectors.toList());
//    }
//
//    /**
//     * 启动流程实例
//     */
//    public Map<String, Object> startProcess(String processDefinitionKey, String initiatorId,
//                                             Map<String, Object> variables) {
//        if (variables == null) {
//            variables = new HashMap<>();
//        }
//        variables.put("initiator", initiatorId);
//
//        ProcessInstance instance = runtimeService.startProcessInstanceByKey(processDefinitionKey, variables);
//
//        Map<String, Object> result = new HashMap<>();
//        result.put("processInstanceId", instance.getId());
//        result.put("processDefinitionId", instance.getProcessDefinitionId());
//        result.put("businessKey", instance.getBusinessKey());
//        log.info("流程实例启动: instanceId={}, definitionKey={}", instance.getId(), processDefinitionKey);
//        return result;
//    }
//
//    /**
//     * 查询用户待办任务
//     */
//    public List<Map<String, Object>> listUserTasks(String assignee) {
//        return taskService.createTaskQuery()
//                .taskAssignee(assignee)
//                .orderByTaskCreateTime().desc()
//                .list()
//                .stream()
//                .map(this::toTaskMap)
//                .collect(Collectors.toList());
//    }
//
//    /**
//     * 查询候选组待办任务
//     */
//    public List<Map<String, Object>> listCandidateTasks(String candidateGroup) {
//        return taskService.createTaskQuery()
//                .taskCandidateGroup(candidateGroup)
//                .orderByTaskCreateTime().desc()
//                .list()
//                .stream()
//                .map(this::toTaskMap)
//                .collect(Collectors.toList());
//    }
//
//    /**
//     * 完成任务（审批通过/驳回）
//     */
//    public void completeTask(String taskId, Map<String, Object> variables) {
//        Task task = taskService.createTaskQuery().taskId(taskId).singleResult();
//        if (task == null) {
//            throw new IllegalArgumentException("任务不存在: " + taskId);
//        }
//        taskService.complete(taskId, variables != null ? variables : Map.of());
//        log.info("任务完成: taskId={}, taskName={}", taskId, task.getName());
//    }
//
//    /**
//     * 认领任务
//     */
//    public void claimTask(String taskId, String userId) {
//        taskService.claim(taskId, userId);
//        log.info("任务认领: taskId={}, userId={}", taskId, userId);
//    }
//
//    private Map<String, Object> toDefinitionMap(ProcessDefinition def) {
//        Map<String, Object> map = new HashMap<>();
//        map.put("id", def.getId());
//        map.put("key", def.getKey());
//        map.put("name", def.getName());
//        map.put("version", def.getVersion());
//        map.put("deploymentId", def.getDeploymentId());
//        map.put("suspended", def.isSuspended());
//        return map;
//    }
//
//    private Map<String, Object> toTaskMap(Task task) {
//        Map<String, Object> map = new HashMap<>();
//        map.put("id", task.getId());
//        map.put("name", task.getName());
//        map.put("assignee", task.getAssignee());
//        map.put("createTime", task.getCreateTime());
//        map.put("processInstanceId", task.getProcessInstanceId());
//        map.put("processDefinitionId", task.getProcessDefinitionId());
//        map.put("taskDefinitionKey", task.getTaskDefinitionKey());
//        return map;
//    }
//}
