package com.lzke.ai.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

@Service
@RequiredArgsConstructor
public class JsonRenderTestService {

    private final ObjectMapper objectMapper;

    private final AtomicReference<Map<String, Object>> currentSpec = new AtomicReference<>(defaultSpec());

    public Map<String, Object> getCurrentSpec() {
        return deepCopy(currentSpec.get());
    }

    public Map<String, Object> replaceSpec(Map<String, Object> spec) {
        Map<String, Object> normalized = normalizeAndValidateSpec(spec);
        currentSpec.set(normalized);
        return deepCopy(normalized);
    }

    public Map<String, Object> updateElement(String elementId, Map<String, Object> patch) {
        if (elementId == null || elementId.isBlank()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "elementId 不能为空");
        }
        if (patch == null || patch.isEmpty()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "patch 不能为空");
        }

        Map<String, Object> spec = deepCopy(currentSpec.get());
        Map<String, Object> elements = getElements(spec);
        Map<String, Object> element = castMap(elements.get(elementId), "目标 element 不存在: " + elementId);

        if (patch.containsKey("type")) {
            Object type = patch.get("type");
            if (!(type instanceof String typeValue) || typeValue.isBlank()) {
                throw new BusinessException(ErrorCode.BAD_REQUEST, "type 必须是非空字符串");
            }
            element.put("type", typeValue);
        }

        if (patch.containsKey("props")) {
            Map<String, Object> propsPatch = castMap(patch.get("props"), "props 必须是对象");
            Map<String, Object> props = castMap(
                    element.computeIfAbsent("props", key -> new LinkedHashMap<>()),
                    "element.props 必须是对象"
            );
            props.putAll(propsPatch);
        }

        if (patch.containsKey("children")) {
            Object children = patch.get("children");
            if (!(children instanceof List<?> childList)) {
                throw new BusinessException(ErrorCode.BAD_REQUEST, "children 必须是字符串数组");
            }
            List<String> normalizedChildren = new ArrayList<>();
            for (Object child : childList) {
                if (!(child instanceof String childId) || childId.isBlank()) {
                    throw new BusinessException(ErrorCode.BAD_REQUEST, "children 中的元素必须是非空字符串");
                }
                normalizedChildren.add(childId);
            }
            element.put("children", normalizedChildren);
        }

        currentSpec.set(spec);
        return deepCopy(spec);
    }

    public Map<String, Object> resetSpec() {
        Map<String, Object> spec = defaultSpec();
        currentSpec.set(spec);
        return deepCopy(spec);
    }

    private Map<String, Object> normalizeAndValidateSpec(Map<String, Object> spec) {
        if (spec == null || spec.isEmpty()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "spec 不能为空");
        }

        Map<String, Object> normalized = deepCopy(spec);
        Object root = normalized.get("root");
        if (!(root instanceof String rootId) || rootId.isBlank()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "json-render spec 必须包含非空 root");
        }

        Map<String, Object> elements = getElements(normalized);
        if (!elements.containsKey(rootId)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "root 指向的 element 不存在: " + rootId);
        }

        for (Map.Entry<String, Object> entry : elements.entrySet()) {
            String elementId = entry.getKey();
            Map<String, Object> element = castMap(entry.getValue(), "element 格式错误: " + elementId);

            Object type = element.get("type");
            if (!(type instanceof String typeValue) || typeValue.isBlank()) {
                throw new BusinessException(ErrorCode.BAD_REQUEST, "element.type 必须是非空字符串: " + elementId);
            }

            Object props = element.get("props");
            if (props == null) {
                element.put("props", new LinkedHashMap<>());
            } else if (!(props instanceof Map<?, ?>)) {
                throw new BusinessException(ErrorCode.BAD_REQUEST, "element.props 必须是对象: " + elementId);
            }

            Object children = element.get("children");
            if (children == null) {
                element.put("children", new ArrayList<>());
            } else if (!(children instanceof List<?> childList)) {
                throw new BusinessException(ErrorCode.BAD_REQUEST, "element.children 必须是数组: " + elementId);
            } else {
                for (Object child : childList) {
                    if (!(child instanceof String childId) || childId.isBlank()) {
                        throw new BusinessException(ErrorCode.BAD_REQUEST, "element.children 只能包含非空字符串: " + elementId);
                    }
                }
            }
        }

        return normalized;
    }

    private Map<String, Object> getElements(Map<String, Object> spec) {
        return castMap(spec.get("elements"), "json-render spec 必须包含 elements 对象");
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> castMap(Object value, String message) {
        if (!(value instanceof Map<?, ?> mapValue)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, message);
        }
        return (Map<String, Object>) mapValue;
    }

    private Map<String, Object> deepCopy(Map<String, Object> source) {
        return objectMapper.convertValue(source, new TypeReference<>() {});
    }

    private static Map<String, Object> defaultSpec() {
        Map<String, Object> elements = new LinkedHashMap<>();

        elements.put("page", element(
                "Card",
                mapOf(
                        "title", "json-render 联调示例",
                        "subtitle", "这份数据由 business-server 测试接口直接返回"
                ),
                List.of("statsCard", "chartCard", "tableCard", "formCard", "listCard")
        ));

        elements.put("statsCard", element(
                "Card",
                mapOf("title", "核心指标"),
                List.of("metricRevenue", "metricConversion", "metricOrders")
        ));
        elements.put("metricRevenue", element("Metric", mapOf("label", "本月营收", "value", 128000, "format", "currency"), List.of()));
        elements.put("metricConversion", element("Metric", mapOf("label", "转化率", "value", 18.6, "format", "percent"), List.of()));
        elements.put("metricOrders", element("Metric", mapOf("label", "订单数", "value", 356, "format", "number"), List.of()));

        elements.put("chartCard", element(
                "Chart",
                mapOf(
                        "title", "近6个月成交趋势",
                        "kind", "line",
                        "option", mapOf(
                                "tooltip", mapOf("trigger", "axis"),
                                "xAxis", mapOf("type", "category", "data", List.of("10月", "11月", "12月", "1月", "2月", "3月")),
                                "yAxis", mapOf("type", "value"),
                                "series", List.of(mapOf(
                                        "name", "成交额",
                                        "type", "line",
                                        "smooth", true,
                                        "data", List.of(82000, 91000, 87000, 105000, 119000, 128000)
                                ))
                        )
                ),
                List.of()
        ));

        elements.put("tableCard", element(
                "Table",
                mapOf(
                        "title", "销售榜单",
                        "columns", List.of("销售", "客户数", "成交额"),
                        "data", List.of(
                                List.of("张三", 18, 32000),
                                List.of("李四", 15, 28000),
                                List.of("王五", 12, 24000)
                        )
                ),
                List.of()
        ));

        elements.put("formCard", element(
                "Form",
                mapOf(
                        "fields", List.of(
                                mapOf("name", "keyword", "label", "关键词", "type", "text", "required", true, "placeholder", "输入搜索关键词"),
                                mapOf(
                                        "name", "system",
                                        "label", "来源系统",
                                        "type", "select",
                                        "options", List.of(
                                                mapOf("label", "全部", "value", "all"),
                                                mapOf("label", "ERP", "value", "erp"),
                                                mapOf("label", "CRM", "value", "crm"),
                                                mapOf("label", "OA", "value", "oa")
                                        )
                                )
                        ),
                        "submitLabel", "提交筛选"
                ),
                List.of()
        ));

        elements.put("listCard", element(
                "List",
                mapOf(
                        "title", "待处理事项",
                        "items", List.of(
                                mapOf(
                                        "id", "task-001",
                                        "title", "跟进重点客户续约",
                                        "description", "客户合同将在 7 天后到期，需要确认报价策略",
                                        "status", "pending",
                                        "assignee", "张三",
                                        "dueDate", "2026-04-05",
                                        "tags", List.of(
                                                mapOf("label", "高优先级", "color", "volcano"),
                                                mapOf("label", "CRM", "color", "cyan")
                                        )
                                ),
                                mapOf(
                                        "id", "task-002",
                                        "title", "审批采购申请",
                                        "description", "等待部门主管审批新的设备采购申请",
                                        "status", "in_progress",
                                        "assignee", "李四",
                                        "dueDate", "2026-04-02",
                                        "tags", List.of(
                                                mapOf("label", "ERP", "color", "blue")
                                        )
                                )
                        ),
                        "emptyText", "暂无待处理事项"
                ),
                List.of()
        ));

        return mapOf("root", "page", "elements", elements);
    }

    private static Map<String, Object> element(String type, Map<String, Object> props, List<String> children) {
        return mapOf(
                "type", type,
                "props", props,
                "children", new ArrayList<>(children)
        );
    }

    private static Map<String, Object> mapOf(Object... entries) {
        if (entries.length % 2 != 0) {
            throw new IllegalArgumentException("entries length must be even");
        }
        Map<String, Object> map = new LinkedHashMap<>();
        for (int i = 0; i < entries.length; i += 2) {
            map.put(String.valueOf(entries[i]), entries[i + 1]);
        }
        return map;
    }
}
