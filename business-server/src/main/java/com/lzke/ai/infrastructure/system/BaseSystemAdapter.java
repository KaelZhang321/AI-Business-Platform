package com.lzke.ai.infrastructure.system;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lzke.ai.domain.entity.SystemAdapter;
import com.lzke.ai.infrastructure.persistence.mapper.SystemAdapterMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * 外部系统适配器基类
 * <p>
 * 内置功能：
 * - 从 system_adapters 表读取系统配置（endpoint、auth、字段映射等）
 * - 通过 RestTemplate 调用外部系统 HTTP API
 * - 简单断路器（Circuit Breaker）：CLOSED → OPEN(3次失败) → HALF_OPEN(30秒后) → CLOSED(成功)
 * <p>
 * 子类只需实现：
 * - getSystemCode()    — 系统编码，对应 system_adapters.code
 * - getSystemName()    — 系统展示名称
 * - mapTaskFields()    — 将外部系统原始字段映射为标准字段
 * - mapActionResponse() — 将操作响应映射为标准格式
 */
public abstract class BaseSystemAdapter {

    protected final Logger log = LoggerFactory.getLogger(getClass());

    @Autowired
    protected SystemAdapterMapper systemAdapterMapper;

    @Autowired
    protected RestTemplate restTemplate;

    @Autowired
    protected ObjectMapper objectMapper;

    // ==================== 断路器状态 ====================

    protected enum CircuitState { CLOSED, OPEN, HALF_OPEN }

    private final AtomicReference<CircuitState> circuitState = new AtomicReference<>(CircuitState.CLOSED);
    private final AtomicInteger failureCount = new AtomicInteger(0);
    private volatile long lastFailureTime = 0;

    /** 连续失败次数阈值，超过后断路器打开 */
    private static final int FAILURE_THRESHOLD = 3;
    /** 断路器打开后的恢复等待时间（毫秒） */
    private static final long RECOVERY_TIMEOUT_MS = 30_000;

    // ==================== 子类必须实现的抽象方法 ====================

    /**
     * 返回系统编码，对应 system_adapters.code 字段
     */
    public abstract String getSystemCode();

    /**
     * 获取系统展示名称
     */
    public abstract String getSystemName();

    /**
     * 将外部系统返回的单条任务原始数据映射为标准字段
     * 标准字段：title, status, priority, externalUrl, description, deadline, sourceId
     */
    protected abstract Map<String, Object> mapTaskFields(Map<String, Object> raw);

    /**
     * 将外部系统的操作响应映射为标准格式
     */
    protected abstract Map<String, Object> mapActionResponse(Map<String, Object> raw);

    // ==================== 公开 API ====================

    /**
     * 拉取指定用户的待办任务
     * <p>
     * 流程：检查断路器 → 从DB加载配置 → HTTP调用外部系统 → 映射字段
     */
    public List<Map<String, Object>> fetchTasks(String userId) {
        // 1. 断路器检查
        if (!isCircuitAllowingRequest()) {
            log.warn("[{}] 断路器已打开，跳过请求", getSystemCode());
            return Collections.emptyList();
        }

        // 2. 从DB加载适配器配置
        SystemAdapter adapterConfig = loadAdapterConfig();
        if (adapterConfig == null) {
            log.warn("[{}] 未找到系统适配器配置或状态非active，返回空列表", getSystemCode());
            return Collections.emptyList();
        }

        try {
            // 3. 解析JSONB配置
            Map<String, Object> config = parseConfig(adapterConfig.getConfig());

            // 4. 构建请求URL
            String tasksPath = (String) config.getOrDefault("tasksPath", "/api/tasks");
            String url = adapterConfig.getEndpoint() + tasksPath + "?userId=" + userId;

            // 5. 构建请求头（含认证信息）
            HttpHeaders headers = buildAuthHeaders(adapterConfig, config);
            headers.setAccept(List.of(MediaType.APPLICATION_JSON));

            // 6. 发起HTTP请求
            HttpEntity<Void> requestEntity = new HttpEntity<>(headers);
            ResponseEntity<String> response = restTemplate.exchange(
                    url, HttpMethod.GET, requestEntity, String.class
            );

            // 7. 解析响应
            List<Map<String, Object>> rawTasks = parseTasksResponse(response.getBody(), config);

            // 8. 映射字段
            List<Map<String, Object>> mappedTasks = new ArrayList<>();
            for (Map<String, Object> raw : rawTasks) {
                mappedTasks.add(mapTaskFields(raw));
            }

            // 9. 成功，重置断路器
            onSuccess();

            log.info("[{}] 成功拉取 {} 条待办任务, userId={}", getSystemCode(), mappedTasks.size(), userId);
            return mappedTasks;

        } catch (RestClientException e) {
            onFailure();
            log.error("[{}] HTTP调用外部系统失败: {}", getSystemCode(), e.getMessage(), e);
            return Collections.emptyList();
        } catch (Exception e) {
            onFailure();
            log.error("[{}] 拉取待办任务异常: {}", getSystemCode(), e.getMessage(), e);
            return Collections.emptyList();
        }
    }

    /**
     * 执行系统操作
     */
    public Map<String, Object> executeAction(String action, Map<String, Object> params) {
        // 1. 断路器检查
        if (!isCircuitAllowingRequest()) {
            log.warn("[{}] 断路器已打开，拒绝执行操作: {}", getSystemCode(), action);
            return Map.of("status", "circuit_open", "message", "系统暂时不可用，请稍后重试");
        }

        // 2. 加载配置
        SystemAdapter adapterConfig = loadAdapterConfig();
        if (adapterConfig == null) {
            return Map.of("status", "error", "message", "未找到系统适配器配置");
        }

        try {
            // 3. 解析配置
            Map<String, Object> config = parseConfig(adapterConfig.getConfig());

            // 4. 构建请求
            String actionsPath = (String) config.getOrDefault("actionsPath", "/api/actions");
            String url = adapterConfig.getEndpoint() + actionsPath + "/" + action;

            HttpHeaders headers = buildAuthHeaders(adapterConfig, config);
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.setAccept(List.of(MediaType.APPLICATION_JSON));

            HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(params, headers);

            // 5. 发起HTTP请求
            ResponseEntity<String> response = restTemplate.exchange(
                    url, HttpMethod.POST, requestEntity, String.class
            );

            // 6. 解析响应
            Map<String, Object> rawResponse = objectMapper.readValue(
                    response.getBody(), new TypeReference<>() {}
            );

            // 7. 成功
            onSuccess();

            return mapActionResponse(rawResponse);

        } catch (RestClientException e) {
            onFailure();
            log.error("[{}] 执行操作失败: action={}, error={}", getSystemCode(), action, e.getMessage(), e);
            return Map.of("status", "error", "message", "外部系统调用失败: " + e.getMessage());
        } catch (Exception e) {
            onFailure();
            log.error("[{}] 执行操作异常: action={}, error={}", getSystemCode(), action, e.getMessage(), e);
            return Map.of("status", "error", "message", "操作执行异常: " + e.getMessage());
        }
    }

    // ==================== 断路器逻辑 ====================

    /**
     * 检查断路器是否允许请求通过
     */
    private boolean isCircuitAllowingRequest() {
        CircuitState state = circuitState.get();

        if (state == CircuitState.CLOSED) {
            return true;
        }

        if (state == CircuitState.OPEN) {
            // 检查是否已过恢复等待时间
            if (Instant.now().toEpochMilli() - lastFailureTime >= RECOVERY_TIMEOUT_MS) {
                // 转入半开状态，允许一次试探请求
                if (circuitState.compareAndSet(CircuitState.OPEN, CircuitState.HALF_OPEN)) {
                    log.info("[{}] 断路器进入HALF_OPEN状态，允许试探请求", getSystemCode());
                }
                return true;
            }
            return false;
        }

        // HALF_OPEN状态允许请求
        return true;
    }

    /**
     * 请求成功时重置断路器
     */
    private void onSuccess() {
        failureCount.set(0);
        CircuitState prev = circuitState.getAndSet(CircuitState.CLOSED);
        if (prev != CircuitState.CLOSED) {
            log.info("[{}] 断路器恢复为CLOSED状态", getSystemCode());
        }
    }

    /**
     * 请求失败时更新断路器
     */
    private void onFailure() {
        lastFailureTime = Instant.now().toEpochMilli();
        int failures = failureCount.incrementAndGet();

        if (circuitState.get() == CircuitState.HALF_OPEN) {
            // 半开状态下失败，立即回到打开状态
            circuitState.set(CircuitState.OPEN);
            log.warn("[{}] HALF_OPEN试探失败，断路器回到OPEN状态", getSystemCode());
        } else if (failures >= FAILURE_THRESHOLD) {
            CircuitState prev = circuitState.getAndSet(CircuitState.OPEN);
            if (prev != CircuitState.OPEN) {
                log.warn("[{}] 连续失败{}次，断路器打开", getSystemCode(), failures);
            }
        }
    }

    // ==================== 内部辅助方法 ====================

    /**
     * 从DB加载适配器配置（按system code查询，状态为active）
     */
    protected SystemAdapter loadAdapterConfig() {
        return systemAdapterMapper.selectOne(
                new LambdaQueryWrapper<SystemAdapter>()
                        .eq(SystemAdapter::getCode, getSystemCode())
                        .eq(SystemAdapter::getStatus, "active")
        );
    }

    /**
     * 解析JSONB配置字段
     */
    @SuppressWarnings("unchecked")
    protected Map<String, Object> parseConfig(String configJson) {
        if (configJson == null || configJson.isBlank()) {
            return Collections.emptyMap();
        }
        try {
            return objectMapper.readValue(configJson, new TypeReference<>() {});
        } catch (Exception e) {
            log.warn("[{}] 解析config JSON失败: {}", getSystemCode(), e.getMessage());
            return Collections.emptyMap();
        }
    }

    /**
     * 根据认证类型构建HTTP请求头
     */
    @SuppressWarnings("unchecked")
    protected HttpHeaders buildAuthHeaders(SystemAdapter adapterConfig, Map<String, Object> config) {
        HttpHeaders headers = new HttpHeaders();
        String authType = adapterConfig.getAuthType();

        if (authType == null) {
            return headers;
        }

        Map<String, Object> authConfig = (Map<String, Object>) config.getOrDefault("auth", Collections.emptyMap());

        switch (authType.toLowerCase()) {
            case "bearer" -> {
                String token = (String) authConfig.getOrDefault("token", "");
                if (!token.isBlank()) {
                    headers.setBearerAuth(token);
                }
            }
            case "basic" -> {
                String username = (String) authConfig.getOrDefault("username", "");
                String password = (String) authConfig.getOrDefault("password", "");
                if (!username.isBlank()) {
                    headers.setBasicAuth(username, password);
                }
            }
            case "api_key" -> {
                String headerName = (String) authConfig.getOrDefault("headerName", "X-API-Key");
                String apiKey = (String) authConfig.getOrDefault("apiKey", "");
                if (!apiKey.isBlank()) {
                    headers.set(headerName, apiKey);
                }
            }
            default -> log.warn("[{}] 不支持的认证类型: {}", getSystemCode(), authType);
        }

        return headers;
    }

    /**
     * 解析任务列表响应
     * 支持通过 config.responsePath 指定数据路径（如 "data.items"）
     */
    @SuppressWarnings("unchecked")
    protected List<Map<String, Object>> parseTasksResponse(String responseBody, Map<String, Object> config) {
        if (responseBody == null || responseBody.isBlank()) {
            return Collections.emptyList();
        }

        try {
            Object parsed = objectMapper.readValue(responseBody, Object.class);

            // 如果配置了响应数据路径，按路径提取
            String responsePath = (String) config.get("responsePath");
            if (responsePath != null && !responsePath.isBlank()) {
                String[] pathParts = responsePath.split("\\.");
                for (String part : pathParts) {
                    if (parsed instanceof Map) {
                        parsed = ((Map<String, Object>) parsed).get(part);
                    } else {
                        break;
                    }
                }
            }

            // 结果应该是一个List
            if (parsed instanceof List<?> list) {
                List<Map<String, Object>> result = new ArrayList<>();
                for (Object item : list) {
                    if (item instanceof Map) {
                        result.add((Map<String, Object>) item);
                    }
                }
                return result;
            }

            log.warn("[{}] 响应数据不是列表格式", getSystemCode());
            return Collections.emptyList();

        } catch (Exception e) {
            log.error("[{}] 解析任务响应失败: {}", getSystemCode(), e.getMessage());
            return Collections.emptyList();
        }
    }

    /**
     * 获取断路器当前状态（用于监控/调试）
     */
    public CircuitState getCircuitState() {
        return circuitState.get();
    }

    /**
     * 获取连续失败次数（用于监控/调试）
     */
    public int getFailureCount() {
        return failureCount.get();
    }

    // ==================== 子类共享工具方法 ====================

    /**
     * 从 Map 中按优先级取第一个非 null 值
     */
    protected Object coalesce(Map<String, Object> map, String... keys) {
        for (String key : keys) {
            Object val = map.get(key);
            if (val != null) return val;
        }
        return null;
    }

    /**
     * 从 Map 中按优先级取第一个非 null 值并转为 String
     */
    protected String getString(Map<String, Object> map, String... keys) {
        Object val = coalesce(map, keys);
        return val != null ? val.toString() : null;
    }
}
