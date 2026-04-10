package com.lzke.ai.application.ui;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lzke.ai.application.dto.UiApiInvokeRequest;
import com.lzke.ai.application.dto.UiJsonRenderInvokeResponse;
import com.lzke.ai.application.dto.UiJsonRenderSubmitActionRequest;
import com.lzke.ai.application.dto.UiJsonRenderSubmitActionResponse;
import com.lzke.ai.application.dto.UiJsonRenderSubmitRequest;
import com.lzke.ai.application.dto.UiJsonRenderSubmitResponse;
import com.lzke.ai.domain.entity.SemanticFieldAlias;
import com.lzke.ai.domain.entity.SemanticFieldDict;
import com.lzke.ai.domain.entity.SemanticFieldValueMap;
import com.lzke.ai.domain.entity.UiApiFlowLog;
import com.lzke.ai.domain.entity.UiApiEndpoint;
import com.lzke.ai.domain.entity.UiApiEndpointRole;
import com.lzke.ai.domain.entity.UiApiSource;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import com.lzke.ai.infrastructure.persistence.mapper.SemanticFieldAliasMapper;
import com.lzke.ai.infrastructure.persistence.mapper.SemanticFieldDictMapper;
import com.lzke.ai.infrastructure.persistence.mapper.SemanticFieldValueMapMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiEndpointMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiEndpointRoleMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiFlowLogMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiSourceMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * UI Builder 接口响应转 json-render 工具服务。
 *
 * <p>这个服务的定位是把“接口原始响应 + 接口定义 + 语义字典配置”转换成
 * 前端可以直接消费的 json-render Spec。
 *
 * <p>它会同时读取 4 类上下文：
 *
 * <ul>
 *     <li>{@link UiApiEndpoint}：接口基础信息、operationSafety、字段编排 JSON</li>
 *     <li>{@link UiApiEndpointRole}：角色级字段编排覆盖（可选）</li>
 *     <li>{@link SemanticFieldAlias}：接口原始字段名到标准字段 key 的映射</li>
 *     <li>{@link SemanticFieldValueMap}：接口值到标准值的转换映射</li>
 * </ul>
 *
 * <p>当前输出遵循项目既有的扁平结构：
 *
 * <pre>
 * {
 *   "root": "page",
 *   "elements": {
 *     "page": { "type": "Card", "props": {...}, "children": [...] }
 *   }
 * }
 * </pre>
 *
 * <p>为了保证通用性，当前工具优先产出前端已经稳定支持的节点类型：
 *
 * <ul>
 *     <li>Card：容器和分组标题</li>
 *     <li>Metric：少量关键数值</li>
 *     <li>Table：结构化二维数据</li>
 *     <li>List：标量列表或简单对象列表</li>
 * </ul>
 *
 * <p>这意味着它不是“完整低代码渲染器”，而是一个能把接口响应稳定落成
 * 页面化 Spec 的通用转换底座。
 */
@Service
@RequiredArgsConstructor
public class UiJsonRenderTransformService {

    private static final Pattern ARRAY_SEGMENT_PATTERN = Pattern.compile("([A-Za-z0-9_\\-]+)\\[(\\d+)]");
    private static final String PAGE_ID = "page";
    private static final int MAX_METRIC_COUNT = 4;

    // ── UI 组件类型 ─────────────────────────────────────────────
    private static final String COMPONENT_CARD = "Card";
    private static final String COMPONENT_TABLE = "Table";
    private static final String COMPONENT_LIST = "List";
    private static final String COMPONENT_METRIC = "Metric";
    private static final String COMPONENT_FORM = "Form";

    // ── 字段类型 ────────────────────────────────────────────────
    private static final String FIELD_TYPE_NUMBER = "number";
    private static final String FIELD_TYPE_TEXT = "text";
    private static final String FIELD_TYPE_BOOLEAN = "boolean";

    // ── UI Props ────────────────────────────────────────────────
    private static final String PROP_TYPE = "type";
    private static final String PROP_PROPS = "props";
    private static final String PROP_CHILDREN = "children";
    private static final String PROP_TITLE = "title";
    private static final String PROP_SUBTITLE = "subtitle";
    private static final String PROP_LABEL = "label";
    private static final String PROP_VALUE = "value";
    private static final String PROP_FORMAT = "format";
    private static final String PROP_COLUMNS = "columns";
    private static final String PROP_DATA = "data";
    private static final String PROP_ITEMS = "items";
    private static final String PROP_EMPTY_TEXT = "emptyText";
    private static final String PROP_ID = "id";
    private static final String PROP_DESCRIPTION = "description";
    private static final String PROP_FIELDS = "fields";
    private static final String PROP_SUBMIT_LABEL = "submitLabel";
    private static final String PROP_INITIAL_VALUES = "initialValues";
    private static final String PROP_ROW_ACTIONS = "rowActions";
    private static final String PROP_ROW_RECORDS = "rowRecords";

    // ── 默认文案 ────────────────────────────────────────────────
    private static final String LABEL_KEY_METRICS = "关键指标";
    private static final String LABEL_FIELD_OVERVIEW = "字段概览";
    private static final String LABEL_LIST_RESULT = "列表结果";
    private static final String LABEL_RAW_RESPONSE = "原始响应";
    private static final String LABEL_NO_DATA = "暂无数据";
    private static final String LABEL_FIELD = "字段";
    private static final String LABEL_VALUE = "值";
    private static final String LABEL_PAYLOAD = "payload";
    private static final String DISPLAY_NULL = "-";
    private static final String ROLE_PREFIX = " / 角色：";

    // ── JSON 路径 ───────────────────────────────────────────────
    private static final String JSON_ROOT = "$";
    private static final String JSON_ROOT_DOT = "$.";
    private static final String FIELD_CONFIG_KEY = "fieldConfig";
    private static final String PAGINATION_CONFIG_KEY = "pagination";
    private static final String VIEW_CONFIG_KEY = "view";
    private static final String VIEW_TYPE_LIST = "list";
    private static final String VIEW_TYPE_DETAIL = "detail";
    private static final String VIEW_TYPE_RAW = "raw";
    private static final String PAGINATION_TARGET_QUERY = "query";
    private static final String PAGINATION_TARGET_BODY = "body";
    private static final List<String> PRIMARY_ARRAY_CANDIDATE_KEYS = List.of("data", "records", "list", "items", "rows");

    private final ObjectMapper objectMapper;
    private final UiHttpInvokeService uiHttpInvokeService;
    private final UiApiEndpointMapper uiApiEndpointMapper;
    private final UiApiEndpointRoleMapper uiApiEndpointRoleMapper;
    private final UiApiSourceMapper uiApiSourceMapper;
    private final UiApiFlowLogMapper uiApiFlowLogMapper;
    private final SemanticFieldDictMapper semanticFieldDictMapper;
    private final SemanticFieldAliasMapper semanticFieldAliasMapper;
    private final SemanticFieldValueMapMapper semanticFieldValueMapMapper;

    /**
     * 根据接口响应直接生成 json-render。
     *
     * <p>这是最常用的入口：已知 `endpointId` 和接口原始响应体时，
     * 直接返回可交给前端渲染的 Spec。
     *
     * @param endpointId 接口定义 ID
     * @param responseBody 接口响应体
     * @return json-render Spec
     */
    public Map<String, Object> transformResponseToJsonRender(String endpointId, Object responseBody) {
        return transformResponseToJsonRender(endpointId, null, responseBody);
    }

    /**
     * 根据接口响应和角色上下文生成 json-render。
     *
     * <p>当同一个接口在不同角色下需要不同的字段编排时，可传入 `roleId`，
     * 服务会自动读取 `ui_api_endpoint_roles.field_orchestration` 作为覆盖层。
     *
     * @param endpointId 接口定义 ID
     * @param roleId 角色 ID，可为空
     * @param responseBody 接口响应体
     * @return json-render Spec
     */
    public Map<String, Object> transformResponseToJsonRender(String endpointId, String roleId, Object responseBody) {
        UiApiEndpoint endpoint = requireEndpoint(endpointId);
        UiApiEndpointRole roleRelation = findRoleRelation(endpointId, roleId);
        JsonNode responseNode = objectMapper.valueToTree(responseBody == null ? Map.of() : responseBody);

        FieldOrchestration orchestration = mergeFieldOrchestration(
                parseFieldOrchestration(endpoint.getFieldOrchestration()),
                parseFieldOrchestration(roleRelation != null ? roleRelation.getFieldOrchestration() : null)
        );

        Map<String, String> aliasToStandardKey = loadAliasMap(endpointId);
        Map<String, SemanticFieldDict> semanticDictByKey = loadSemanticDictMap();
        Map<String, Map<String, String>> semanticValueMapByKey = loadValueMap(endpointId);

        return buildSpec(endpoint, roleRelation, responseNode, orchestration, aliasToStandardKey, semanticDictByKey, semanticValueMapByKey);
    }

    /**
     * 先按接口定义发起真实调用，再把响应转换成 json-render 返回给前端。
     *
     * <p>该方法用于你当前最直接的运行时场景：
     *
     * <ol>
     *     <li>前端给出一个 endpointId 和可选请求参数</li>
     *     <li>服务端通过 {@link UiHttpInvokeService} 调用真实接口</li>
     *     <li>把“真实响应体 + json-render spec”一起返回给前端</li>
     * </ol>
     *
     * <p>这样前端既能拿到接口原始值，也能直接拿到渲染结果，不需要再额外发第二次请求做转换。
     *
     * @param endpointId 接口定义 ID
     * @param roleId 角色 ID，可为空
     * @param request 运行时调用参数
     * @return 包含原始响应和 json-render spec 的聚合响应
     */
    public UiJsonRenderInvokeResponse invokeAndTransformResponse(String endpointId, String roleId, UiApiInvokeRequest request) {
        UiApiEndpoint endpoint = requireEndpoint(endpointId);
        UiApiSource source = requireSource(endpoint.getSourceId());
        UiApiEndpointRole roleRelation = findRoleRelation(endpointId, roleId);
        validateRuntimeInvokeTarget(source, endpoint);

        Map<String, Object> queryParams = request != null ? safeCopyMap(request.getQueryParams()) : new LinkedHashMap<>();
        Object requestBody = resolveInvokeBody(endpoint, request);
        Map<String, Object> requestHeaders = request != null ? safeCopyMap(request.getHeaders()) : new LinkedHashMap<>();

        UiHttpInvokeService.HttpExecutionResult executionResult = uiHttpInvokeService.execute(
                source,
                endpoint,
                requestHeaders,
                queryParams,
                requestBody
        );

        UiApiFlowLog flowLog = createFlowLog(
                endpointId,
                request != null ? request.getFlowNum() : null,
                request != null ? request.getCreatedBy() : null,
                request != null ? request.getCreatedByName() : null,
                executionResult
        );

        if (!executionResult.success()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, defaultIfBlank(executionResult.errorMessage(), "接口调用失败"));
        }

        Object parsedResponseBody = parsePossiblyJson((String) executionResult.responseBody());
        Map<String, Object> jsonRender = transformResponseToJsonRender(endpointId, roleId, parsedResponseBody);
        FieldOrchestration orchestration = mergeFieldOrchestration(
                parseFieldOrchestration(endpoint.getFieldOrchestration()),
                parseFieldOrchestration(roleRelation != null ? roleRelation.getFieldOrchestration() : null)
        );
        PaginationBinding runtimePaginationBinding = resolveRuntimePaginationBinding(endpoint, orchestration.pagination());
        attachRuntimePaginationAction(
                jsonRender,
                endpointId,
                roleId,
                request != null ? request.getFlowNum() : null,
                queryParams,
                safeCopyObjectMap(requestBody),
                runtimePaginationBinding
        );
        return new UiJsonRenderInvokeResponse(
                endpointId,
                roleId,
                request != null ? request.getFlowNum() : null,
                flowLog.getId(),
                parsedResponseBody,
                jsonRender
        );
    }

    /**
     * 按标准语义表单值驱动多个接口顺序提交。
     *
     * <p>该方法解决“一个 json-render 表单背后要调用多个三方接口”的场景。
     * 前端提交的不是每个接口的原始字段，而是标准语义字段；服务端会根据：
     *
     * <ul>
     *     <li>`semantic_field_alias`：标准字段 -> 接口原始字段</li>
     *     <li>`semantic_field_value_map`：标准值 -> 接口原始值</li>
     * </ul>
     *
     * <p>自动把表单值转换成每个接口真正需要的 query/body/header，再依次调用。
     *
     * @param request 表单提交请求
     * @return 每个动作的执行结果汇总
     */
    public UiJsonRenderSubmitResponse submitSemanticForm(UiJsonRenderSubmitRequest request) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "提交请求不能为空");
        }
        if (request.getActions() == null || request.getActions().isEmpty()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "actions 不能为空");
        }

        Map<String, Object> semanticValues = request.getSemanticValues() != null
                ? new LinkedHashMap<>(request.getSemanticValues())
                : new LinkedHashMap<>();

        List<UiJsonRenderSubmitActionResponse> results = new ArrayList<>();
        boolean overallSuccess = true;
        for (UiJsonRenderSubmitActionRequest action : request.getActions()) {
            UiJsonRenderSubmitActionResponse actionResponse = submitSingleAction(request, semanticValues, action);
            results.add(actionResponse);
            if (!actionResponse.isSuccess()) {
                overallSuccess = false;
            }
        }
        return new UiJsonRenderSubmitResponse(request.getFlowNum(), overallSuccess, results);
    }

    private UiJsonRenderSubmitActionResponse submitSingleAction(
            UiJsonRenderSubmitRequest request,
            Map<String, Object> semanticValues,
            UiJsonRenderSubmitActionRequest action
    ) {
        if (action == null || !StringUtils.hasText(action.getEndpointId())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "提交动作必须包含 endpointId");
        }

        UiApiEndpoint endpoint = requireEndpoint(action.getEndpointId());
        UiApiSource source = requireSource(endpoint.getSourceId());
        validateRuntimeInvokeTarget(source, endpoint);

        Map<String, String> aliasToStandardKey = loadAliasMap(endpoint.getId());
        Map<String, Map<String, String>> standardToRawValueMap = loadReverseValueMap(endpoint.getId());

        Map<String, Object> resolvedQueryParams = resolveSemanticPayload(
                action.getQueryKeys(),
                semanticValues,
                aliasToStandardKey,
                standardToRawValueMap
        );
        resolvedQueryParams.putAll(safeCopyMap(action.getStaticQueryParams()));

        Map<String, Object> resolvedHeaders = resolveSemanticPayload(
                action.getHeaderKeys(),
                semanticValues,
                aliasToStandardKey,
                standardToRawValueMap
        );
        resolvedHeaders.putAll(safeCopyMap(action.getStaticHeaders()));

        Object resolvedBody = resolveSubmitBody(
                endpoint,
                action,
                semanticValues,
                aliasToStandardKey,
                standardToRawValueMap
        );

        UiHttpInvokeService.HttpExecutionResult executionResult = uiHttpInvokeService.execute(
                source,
                endpoint,
                resolvedHeaders,
                resolvedQueryParams,
                resolvedBody
        );

        UiApiFlowLog flowLog = createFlowLog(
                endpoint.getId(),
                request.getFlowNum(),
                request.getCreatedBy(),
                request.getCreatedByName(),
                executionResult
        );

        Object responseBody = executionResult.responseBody() != null
                ? parsePossiblyJson((String) executionResult.responseBody())
                : null;

        return new UiJsonRenderSubmitActionResponse(
                endpoint.getId(),
                action.getRoleId(),
                flowLog.getId(),
                executionResult.requestUrl(),
                executionResult.success(),
                responseBody,
                executionResult.errorMessage()
        );
    }

    private Map<String, Object> resolveSemanticPayload(
            List<String> rawKeys,
            Map<String, Object> semanticValues,
            Map<String, String> aliasToStandardKey,
            Map<String, Map<String, String>> standardToRawValueMap
    ) {
        Map<String, Object> payload = new LinkedHashMap<>();
        if (rawKeys == null || rawKeys.isEmpty()) {
            return payload;
        }
        for (String rawKey : rawKeys) {
            if (!StringUtils.hasText(rawKey)) {
                continue;
            }
            String trimmedRawKey = rawKey.trim();
            String standardKey = resolveStandardKeyForSubmit(trimmedRawKey, aliasToStandardKey, semanticValues);
            if (!StringUtils.hasText(standardKey) || !semanticValues.containsKey(standardKey)) {
                continue;
            }
            Object standardValue = semanticValues.get(standardKey);
            payload.put(trimmedRawKey, convertStandardValueToRaw(standardKey, standardValue, standardToRawValueMap));
        }
        return payload;
    }

    private Object resolveSubmitBody(
            UiApiEndpoint endpoint,
            UiJsonRenderSubmitActionRequest action,
            Map<String, Object> semanticValues,
            Map<String, String> aliasToStandardKey,
            Map<String, Map<String, String>> standardToRawValueMap
    ) {
        Object seedBody = resolveSampleBodyForAction(endpoint, action);
        Map<String, Object> bodyMap = bodyToMap(seedBody);
        bodyMap.putAll(safeCopyMap(action.getStaticBody()));
        bodyMap.putAll(resolveSemanticPayload(action.getBodyKeys(), semanticValues, aliasToStandardKey, standardToRawValueMap));
        return bodyMap.isEmpty() ? seedBody : bodyMap;
    }

    private Object resolveSampleBodyForAction(UiApiEndpoint endpoint, UiJsonRenderSubmitActionRequest action) {
        if (action != null && Boolean.FALSE.equals(action.getUseSampleWhenEmpty())) {
            return null;
        }
        return parsePossiblyJson(endpoint.getSampleRequest());
    }

    private Map<String, Object> bodyToMap(Object body) {
        if (body == null) {
            return new LinkedHashMap<>();
        }
        if (body instanceof Map<?, ?> bodyMap) {
            Map<String, Object> normalized = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : bodyMap.entrySet()) {
                normalized.put(String.valueOf(entry.getKey()), entry.getValue());
            }
            return normalized;
        }
        try {
            return objectMapper.convertValue(body, new TypeReference<>() {});
        } catch (IllegalArgumentException ex) {
            return new LinkedHashMap<>();
        }
    }

    private Object convertStandardValueToRaw(
            String standardKey,
            Object standardValue,
            Map<String, Map<String, String>> standardToRawValueMap
    ) {
        if (standardValue == null) {
            return null;
        }
        if (standardValue instanceof Collection<?> collection) {
            List<Object> converted = new ArrayList<>();
            for (Object item : collection) {
                converted.add(convertStandardValueToRaw(standardKey, item, standardToRawValueMap));
            }
            return converted;
        }
        Map<String, String> rawValueMap = standardToRawValueMap.getOrDefault(standardKey, Map.of());
        String rawValue = rawValueMap.get(String.valueOf(standardValue));
        return StringUtils.hasText(rawValue) ? rawValue : standardValue;
    }

    private String resolveStandardKeyForSubmit(
            String rawKey,
            Map<String, String> aliasToStandardKey,
            Map<String, Object> semanticValues
    ) {
        String standardKey = resolveStandardKey(rawKey, aliasToStandardKey);
        if (StringUtils.hasText(standardKey)) {
            return standardKey;
        }
        return semanticValues.containsKey(rawKey) ? rawKey : null;
    }

    private boolean isPaginationGroup(FieldGroup group) {
        if (group == null) {
            return false;
        }
        if ("pagination".equalsIgnoreCase(defaultIfBlank(group.groupKey(), ""))) {
            return true;
        }
        if ("分页信息".equals(group.label())) {
            return true;
        }
        if (group.fields() == null || group.fields().isEmpty()) {
            return false;
        }
        Set<String> paginationKeys = Set.of("total", "size", "current", "pages", "data.total", "data.size", "data.current", "data.pages");
        for (FieldDefinition field : group.fields()) {
            if (field == null || !StringUtils.hasText(field.rawKey())) {
                return false;
            }
            if (!paginationKeys.contains(field.rawKey())) {
                return false;
            }
        }
        return true;
    }

    private void addPaginationProps(Map<String, Object> tableProps, PrimaryArrayResult primaryArrayResult) {
        if (primaryArrayResult == null || primaryArrayResult.containerNode() == null || !primaryArrayResult.containerNode().isObject()) {
            return;
        }
        JsonNode container = primaryArrayResult.containerNode();
        JsonNode totalNode = container.path("total");
        JsonNode currentNode = container.path("current");
        JsonNode sizeNode = container.path("size");
        JsonNode pagesNode = container.path("pages");
        if (!totalNode.isNumber() && !currentNode.isNumber() && !sizeNode.isNumber() && !pagesNode.isNumber()) {
            return;
        }
        Map<String, Object> pagination = new LinkedHashMap<>();
        if (currentNode.isNumber()) {
            pagination.put("current", currentNode.asInt());
        }
        if (sizeNode.isNumber()) {
            pagination.put("pageSize", sizeNode.asInt());
        }
        if (totalNode.isNumber()) {
            pagination.put("total", totalNode.asLong());
        }
        if (pagesNode.isNumber()) {
            pagination.put("pages", pagesNode.asInt());
        }
        pagination.put("mode", "server");
        pagination.put("showSizeChanger", false);
        tableProps.put("pagination", pagination);
    }

    private void attachRuntimePaginationAction(
            Map<String, Object> jsonRender,
            String endpointId,
            String roleId,
            String flowNum,
            Map<String, Object> baseQueryParams,
            Map<String, Object> baseBody,
            PaginationBinding paginationBinding
    ) {
        if (jsonRender == null || !jsonRender.containsKey("elements")) {
            return;
        }
        Object elementsValue = jsonRender.get("elements");
        if (!(elementsValue instanceof Map<?, ?> rawElements)) {
            return;
        }
        for (Map.Entry<?, ?> entry : rawElements.entrySet()) {
            Object elementValue = entry.getValue();
            if (!(elementValue instanceof Map<?, ?> rawElement)) {
                continue;
            }
            Object type = rawElement.get(PROP_TYPE);
            if (!Objects.equals(COMPONENT_TABLE, type)) {
                continue;
            }
            Object propsValue = rawElement.get(PROP_PROPS);
            if (!(propsValue instanceof Map<?, ?> rawProps)) {
                continue;
            }
            Object paginationValue = rawProps.get("pagination");
            if (!(paginationValue instanceof Map<?, ?> rawPagination)) {
                continue;
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> pagination = (Map<String, Object>) rawPagination;
            PaginationBinding resolvedBinding = paginationBinding != null ? paginationBinding : PaginationBinding.defaultBinding();
            pagination.put("action", mapOf(
                    "type", "invokeEndpointRender",
                    "endpointId", endpointId,
                    "roleId", roleId,
                    "flowNum", flowNum,
                    "currentKey", resolvedBinding.currentKey(),
                    "sizeKey", resolvedBinding.sizeKey(),
                    "requestTarget", resolvedBinding.requestTarget(),
                    "queryParams", safeCopyMap(baseQueryParams),
                    "body", safeCopyMap(baseBody)
            ));
        }
    }

    private Map<String, Object> buildSpec(
            UiApiEndpoint endpoint,
            UiApiEndpointRole roleRelation,
            JsonNode responseNode,
            FieldOrchestration orchestration,
            Map<String, String> aliasToStandardKey,
            Map<String, SemanticFieldDict> semanticDictByKey,
            Map<String, Map<String, String>> semanticValueMapByKey
    ) {
        Map<String, Object> elements = new LinkedHashMap<>();
        List<String> pageChildren = new ArrayList<>();
        AtomicInteger sequence = new AtomicInteger(1);
        PrimaryArrayResult primaryArrayResult = findPrimaryArrayResult(responseNode);
        ViewBinding resolvedView = resolveViewBinding(endpoint, orchestration.view(), responseNode, primaryArrayResult);
        JsonNode detailNode = resolveDetailNode(responseNode, resolvedView);

        List<ResolvedField> renderFields = resolveConfiguredFields(
                orchestration.render(),
                orchestration.ignore(),
                responseNode,
                aliasToStandardKey,
                semanticDictByKey,
                semanticValueMapByKey
        );
        appendPassthroughFields(
                renderFields,
                orchestration.passthrough(),
                orchestration.ignore(),
                responseNode,
                aliasToStandardKey,
                semanticDictByKey,
                semanticValueMapByKey
        );

        addConfiguredSections(elements, pageChildren, renderFields, orchestration.groups(), responseNode, orchestration.ignore(), aliasToStandardKey,
                semanticDictByKey, semanticValueMapByKey, sequence);

        if (pageChildren.isEmpty()) {
            if (VIEW_TYPE_LIST.equals(resolvedView.type())) {
                addPrimaryArraySection(elements, pageChildren, endpoint, primaryArrayResult, orchestration.ignore(), aliasToStandardKey,
                        semanticDictByKey, semanticValueMapByKey, orchestration.actions(), sequence);
            } else if (VIEW_TYPE_DETAIL.equals(resolvedView.type())) {
                addDetailObjectSection(elements, pageChildren, detailNode, resolvedView.dataPath(), orchestration.ignore(), aliasToStandardKey,
                        semanticDictByKey, semanticValueMapByKey, sequence);
            }
        }

        if (VIEW_TYPE_DETAIL.equals(resolvedView.type())) {
            addFormSection(elements, pageChildren, orchestration.form(), detailNode, aliasToStandardKey, semanticDictByKey, semanticValueMapByKey, sequence);
        }

        if (pageChildren.isEmpty()) {
            addFallbackPayloadSection(elements, pageChildren, responseNode, sequence);
        }

        elements.put(PAGE_ID, element(
                COMPONENT_CARD,
                mapOf(
                        PROP_TITLE, defaultIfBlank(endpoint.getName(), endpoint.getPath()),
                        PROP_SUBTITLE, buildSubtitle(endpoint, roleRelation)
                ),
                pageChildren
        ));

        return mapOf(
                "root", PAGE_ID,
                "elements", elements
        );  // root / elements 是 json-render 协议固定 key，不再额外提取常量
    }

    private void addConfiguredSections(
            Map<String, Object> elements,
            List<String> pageChildren,
            List<ResolvedField> renderFields,
            List<FieldGroup> groups,
            JsonNode responseNode,
            Set<String> ignore,
            Map<String, String> aliasToStandardKey,
            Map<String, SemanticFieldDict> semanticDictByKey,
            Map<String, Map<String, String>> semanticValueMapByKey,
            AtomicInteger sequence
    ) {
        addMetricSection(elements, pageChildren, renderFields, sequence);
        addRenderTable(elements, pageChildren, renderFields, sequence);
        addGroupSections(elements, pageChildren, groups, responseNode, ignore, aliasToStandardKey, semanticDictByKey, semanticValueMapByKey, sequence);
    }

    private void addMetricSection(
            Map<String, Object> elements,
            List<String> pageChildren,
            List<ResolvedField> renderFields,
            AtomicInteger sequence
    ) {
        List<ResolvedField> metrics = renderFields.stream()
                .filter(ResolvedField::isMetricCandidate)
                .limit(MAX_METRIC_COUNT)
                .toList();
        if (metrics.isEmpty()) {
            return;
        }

        String metricCardId = nextId("metricsCard", sequence);
        List<String> metricChildren = new ArrayList<>();
        for (ResolvedField field : metrics) {
            String metricId = nextId("metric", sequence);
            elements.put(metricId, element(
                    COMPONENT_METRIC,
                    mapOf(
                            PROP_LABEL, field.label(),
                            PROP_VALUE, field.metricValue(),
                            PROP_FORMAT, field.metricFormat()
                    ),
                    List.of()
            ));
            metricChildren.add(metricId);
        }
        elements.put(metricCardId, element(COMPONENT_CARD, mapOf(PROP_TITLE, LABEL_KEY_METRICS), metricChildren));
        pageChildren.add(metricCardId);
    }

    private void addRenderTable(
            Map<String, Object> elements,
            List<String> pageChildren,
            List<ResolvedField> renderFields,
            AtomicInteger sequence
    ) {
        List<List<Object>> rows = new ArrayList<>();
        for (ResolvedField field : renderFields) {
            if (field.isMetricCandidate()) {
                continue;
            }
            rows.add(List.of(field.label(), field.displayValue()));
        }
        if (rows.isEmpty()) {
            return;
        }

        String tableId = nextId("renderTable", sequence);
        elements.put(tableId, element(
                COMPONENT_TABLE,
                mapOf(
                        PROP_TITLE, LABEL_FIELD_OVERVIEW,
                        PROP_COLUMNS, List.of(LABEL_FIELD, LABEL_VALUE),
                        PROP_DATA, rows
                ),
                List.of()
        ));
        pageChildren.add(tableId);
    }

    private void addGroupSections(
            Map<String, Object> elements,
            List<String> pageChildren,
            List<FieldGroup> groups,
            JsonNode responseNode,
            Set<String> ignore,
            Map<String, String> aliasToStandardKey,
            Map<String, SemanticFieldDict> semanticDictByKey,
            Map<String, Map<String, String>> semanticValueMapByKey,
            AtomicInteger sequence
    ) {
        for (FieldGroup group : groups) {
            if (isPaginationGroup(group)) {
                continue;
            }
            List<ResolvedField> fields = resolveConfiguredFields(group.fields(), ignore, responseNode, aliasToStandardKey,
                    semanticDictByKey, semanticValueMapByKey);
            if (fields.isEmpty()) {
                continue;
            }

            List<List<Object>> rows = new ArrayList<>();
            for (ResolvedField field : fields) {
                rows.add(List.of(field.label(), field.displayValue()));
            }

            String tableId = nextId(group.groupKey() + "Table", sequence);
            String cardId = nextId(group.groupKey() + "Card", sequence);
            elements.put(tableId, element(
                    COMPONENT_TABLE,
                    mapOf(
                            PROP_COLUMNS, List.of(LABEL_FIELD, LABEL_VALUE),
                            PROP_DATA, rows
                    ),
                    List.of()
            ));
            elements.put(cardId, element(
                    COMPONENT_CARD,
                    mapOf(PROP_TITLE, group.label()),
                    List.of(tableId)
            ));
            pageChildren.add(cardId);
        }
    }

    private void addPrimaryArraySection(
            Map<String, Object> elements,
            List<String> pageChildren,
            UiApiEndpoint endpoint,
            PrimaryArrayResult primaryArrayResult,
            Set<String> ignore,
            Map<String, String> aliasToStandardKey,
            Map<String, SemanticFieldDict> semanticDictByKey,
            Map<String, Map<String, String>> semanticValueMapByKey,
            ActionsBinding actionsBinding,
            AtomicInteger sequence
    ) {
        JsonNode arrayNode = primaryArrayResult != null ? primaryArrayResult.arrayNode() : null;
        if (arrayNode == null || !arrayNode.isArray() || arrayNode.isEmpty()) {
            return;
        }

        JsonNode first = arrayNode.get(0);
        if (first == null || first.isMissingNode()) {
            return;
        }

        if (first.isObject()) {
            List<String> keys = new ArrayList<>();
            first.fieldNames().forEachRemaining(keys::add);
            keys.removeIf(ignore::contains);
            if (keys.isEmpty()) {
                return;
            }

            List<Object> columns = new ArrayList<>();
            for (String key : keys) {
                columns.add(resolveFieldLabel(key, aliasToStandardKey, semanticDictByKey));
            }
            List<List<Object>> rows = new ArrayList<>();
            List<Map<String, Object>> rowRecords = new ArrayList<>();
            for (JsonNode item : arrayNode) {
                if (!item.isObject()) {
                    continue;
                }
                rowRecords.add(toObjectMap(item));
                List<Object> row = new ArrayList<>();
                for (String key : keys) {
                    row.add(normalizeDisplayValue(item.path(key), resolveStandardKey(key, aliasToStandardKey), semanticValueMapByKey));
                }
                rows.add(row);
            }
            String tableId = nextId("primaryList", sequence);
            Map<String, Object> tableProps = mapOf(
                    PROP_TITLE, LABEL_LIST_RESULT,
                    PROP_COLUMNS, columns,
                    PROP_DATA, rows,
                    PROP_ROW_RECORDS, rowRecords
            );
            addPaginationProps(tableProps, primaryArrayResult);
            attachRowActions(tableProps, actionsBinding);
            elements.put(tableId, element(
                    COMPONENT_TABLE,
                    tableProps,
                    List.of()
            ));
            pageChildren.add(tableId);
            return;
        }

        List<Object> items = new ArrayList<>();
        for (JsonNode item : arrayNode) {
            items.add(mapOf(
                    PROP_ID, nextId("listItem", sequence),
                    PROP_TITLE, normalizeDisplayValue(item, null, semanticValueMapByKey),
                    PROP_DESCRIPTION, defaultIfBlank(endpoint.getSummary(), endpoint.getPath())
            ));
        }
        String listId = nextId("primaryScalarList", sequence);
        elements.put(listId, element(
                COMPONENT_LIST,
                mapOf(
                        PROP_TITLE, LABEL_LIST_RESULT,
                        PROP_ITEMS, items,
                        PROP_EMPTY_TEXT, LABEL_NO_DATA
                ),
                List.of()
        ));
        pageChildren.add(listId);
    }

    private void attachRowActions(Map<String, Object> tableProps, ActionsBinding actionsBinding) {
        if (tableProps == null || actionsBinding == null || actionsBinding.rowActions().isEmpty()) {
            return;
        }
        List<Map<String, Object>> rowActions = new ArrayList<>();
        for (RowActionBinding action : actionsBinding.rowActions()) {
            rowActions.add(action.toMap());
        }
        if (!rowActions.isEmpty()) {
            tableProps.put(PROP_ROW_ACTIONS, rowActions);
        }
    }

    private void addFormSection(
            Map<String, Object> elements,
            List<String> pageChildren,
            FormBinding formBinding,
            JsonNode detailNode,
            Map<String, String> aliasToStandardKey,
            Map<String, SemanticFieldDict> semanticDictByKey,
            Map<String, Map<String, String>> semanticValueMapByKey,
            AtomicInteger sequence
    ) {
        if (formBinding == null || formBinding.fields().isEmpty()) {
            return;
        }

        List<Map<String, Object>> fields = new ArrayList<>();
        Map<String, Object> initialValues = new LinkedHashMap<>();
        for (FormFieldBinding field : formBinding.fields()) {
            fields.add(field.toMap(resolveFormFieldOptions(field, semanticDictByKey, semanticValueMapByKey)));
            Object initialValue = resolveFormInitialValue(field, detailNode, aliasToStandardKey, semanticValueMapByKey);
            String fieldName = defaultIfBlank(trimToNull(field.name()), defaultIfBlank(trimToNull(field.standardKey()), trimToNull(field.rawKey())));
            if (StringUtils.hasText(fieldName) && initialValue != null) {
                initialValues.put(fieldName, initialValue);
            }
        }

        String formId = nextId("form", sequence);
        Map<String, Object> props = new LinkedHashMap<>();
        if (StringUtils.hasText(formBinding.title())) {
            props.put(PROP_TITLE, formBinding.title());
        }
        props.put(PROP_FIELDS, fields);
        props.put(PROP_SUBMIT_LABEL, defaultIfBlank(formBinding.submitLabel(), "提交"));
        if (!initialValues.isEmpty()) {
            props.put(PROP_INITIAL_VALUES, initialValues);
        }
        if (formBinding.submitAction() != null && !formBinding.submitAction().isEmpty()) {
            props.put("submitAction", formBinding.submitAction());
        }
        if (StringUtils.hasText(formBinding.mode())) {
            props.put("mode", formBinding.mode());
        }
        elements.put(formId, element(COMPONENT_FORM, props, List.of()));
        pageChildren.add(formId);
    }

    private List<Map<String, Object>> resolveFormFieldOptions(
            FormFieldBinding field,
            Map<String, SemanticFieldDict> semanticDictByKey,
            Map<String, Map<String, String>> semanticValueMapByKey
    ) {
        if (field == null || !isSelectField(field.type())) {
            return field != null ? field.options() : new ArrayList<>();
        }
        if (field.options() != null && !field.options().isEmpty()) {
            return field.options();
        }

        LinkedHashSet<String> semanticValues = new LinkedHashSet<>();
        if (StringUtils.hasText(field.standardKey())) {
            Map<String, String> mappedValues = semanticValueMapByKey.get(field.standardKey());
            if (mappedValues != null) {
                semanticValues.addAll(mappedValues.values());
            }
            SemanticFieldDict dict = semanticDictByKey.get(field.standardKey());
            semanticValues.addAll(parseStandardValuesFromDict(dict));
        }

        List<Map<String, Object>> options = new ArrayList<>();
        for (String semanticValue : semanticValues) {
            if (!StringUtils.hasText(semanticValue)) {
                continue;
            }
            options.add(mapOf("label", semanticValue, "value", semanticValue));
        }
        return options;
    }

    private void addDetailObjectSection(
            Map<String, Object> elements,
            List<String> pageChildren,
            JsonNode detailNode,
            String dataPath,
            Set<String> ignore,
            Map<String, String> aliasToStandardKey,
            Map<String, SemanticFieldDict> semanticDictByKey,
            Map<String, Map<String, String>> semanticValueMapByKey,
            AtomicInteger sequence
    ) {
        if (detailNode == null || detailNode.isMissingNode() || detailNode.isNull() || !detailNode.isObject()) {
            return;
        }

        List<List<Object>> rows = new ArrayList<>();
        detailNode.fieldNames().forEachRemaining(fieldName -> {
            if (isIgnoredField(ignore, fieldName, dataPath)) {
                return;
            }
            JsonNode fieldNode = detailNode.path(fieldName);
            String rawKey = buildChildPath(dataPath, fieldName);
            rows.add(List.of(
                    resolveFieldLabel(rawKey, aliasToStandardKey, semanticDictByKey),
                    normalizeDisplayValue(fieldNode, resolveStandardKey(rawKey, aliasToStandardKey), semanticValueMapByKey)
            ));
        });

        if (rows.isEmpty()) {
            return;
        }

        String tableId = nextId("detailTable", sequence);
        elements.put(tableId, element(
                COMPONENT_TABLE,
                mapOf(
                        PROP_COLUMNS, List.of(LABEL_FIELD, LABEL_VALUE),
                        PROP_DATA, rows
                ),
                List.of()
        ));
        pageChildren.add(tableId);
    }

    private void addFallbackPayloadSection(
            Map<String, Object> elements,
            List<String> pageChildren,
            JsonNode responseNode,
            AtomicInteger sequence
    ) {
        String tableId = nextId("rawPayload", sequence);
        elements.put(tableId, element(
                COMPONENT_TABLE,
                mapOf(
                        PROP_TITLE, LABEL_RAW_RESPONSE,
                        PROP_COLUMNS, List.of(LABEL_FIELD, LABEL_VALUE),
                        PROP_DATA, List.of(List.of(LABEL_PAYLOAD, stringifyNode(responseNode)))
                ),
                List.of()
        ));
        pageChildren.add(tableId);
    }

    private void appendPassthroughFields(
            List<ResolvedField> target,
            Set<String> passthrough,
            Set<String> ignore,
            JsonNode responseNode,
            Map<String, String> aliasToStandardKey,
            Map<String, SemanticFieldDict> semanticDictByKey,
            Map<String, Map<String, String>> semanticValueMapByKey
    ) {
        Set<String> existingRawKeys = new LinkedHashSet<>();
        for (ResolvedField field : target) {
            existingRawKeys.add(field.rawKey());
        }

        List<FieldDefinition> passthroughDefinitions = new ArrayList<>();
        for (String rawKey : passthrough) {
            if (ignore.contains(rawKey) || existingRawKeys.contains(rawKey)) {
                continue;
            }
            passthroughDefinitions.add(new FieldDefinition(rawKey, null, null, null));
        }
        target.addAll(resolveConfiguredFields(passthroughDefinitions, ignore, responseNode, aliasToStandardKey, semanticDictByKey, semanticValueMapByKey));
    }

    private List<ResolvedField> resolveConfiguredFields(
            List<FieldDefinition> definitions,
            Set<String> ignore,
            JsonNode responseNode,
            Map<String, String> aliasToStandardKey,
            Map<String, SemanticFieldDict> semanticDictByKey,
            Map<String, Map<String, String>> semanticValueMapByKey
    ) {
        List<ResolvedField> result = new ArrayList<>();
        for (FieldDefinition definition : definitions) {
            if (!StringUtils.hasText(definition.rawKey())) {
                continue;
            }
            if (ignore.contains(definition.rawKey())) {
                continue;
            }

            JsonNode fieldNode = extractJsonPath(responseNode, definition.rawKey());
            if (fieldNode == null || fieldNode.isMissingNode() || fieldNode.isNull()) {
                continue;
            }

            String standardKey = defaultIfBlank(
                    trimToNull(definition.standardKey()),
                    resolveStandardKey(definition.rawKey(), aliasToStandardKey)
            );
            SemanticFieldDict dict = semanticDictByKey.get(standardKey);
            String label = defaultIfBlank(trimToNull(definition.label()), dict != null ? dict.getLabel() : humanizeKey(definition.rawKey()));
            String type = defaultIfBlank(trimToNull(definition.type()), dict != null ? dict.getFieldType() : inferFieldType(fieldNode));
            String displayValue = normalizeDisplayValue(fieldNode, standardKey, semanticValueMapByKey);

            result.add(new ResolvedField(
                    definition.rawKey(),
                    standardKey,
                    label,
                    type,
                    fieldNode,
                    displayValue
            ));
        }
        return result;
    }

    private FieldOrchestration parseFieldOrchestration(String json) {
        if (!StringUtils.hasText(json)) {
            return FieldOrchestration.empty();
        }
        try {
            JsonNode root = objectMapper.readTree(json);
            JsonNode fieldConfig = root.path(FIELD_CONFIG_KEY);
            if (!fieldConfig.isObject()) {
                return FieldOrchestration.empty();
            }
            return new FieldOrchestration(
                    toStringSet(fieldConfig.path("ignore")),
                    toStringSet(fieldConfig.path("passthrough")),
                    parseGroups(fieldConfig.path("groups")),
                    parseFields(fieldConfig.path("render")),
                    parsePaginationBinding(fieldConfig.path(PAGINATION_CONFIG_KEY)),
                    parseViewBinding(fieldConfig.path(VIEW_CONFIG_KEY)),
                    parseActionsBinding(root.path("actions")),
                    parseFormBinding(root.path("form"))
            );
        } catch (JsonProcessingException ex) {
            return FieldOrchestration.empty();
        }
    }

    private FieldOrchestration mergeFieldOrchestration(FieldOrchestration base, FieldOrchestration override) {
        LinkedHashSet<String> ignore = new LinkedHashSet<>(base.ignore());
        ignore.addAll(override.ignore());

        LinkedHashSet<String> passthrough = new LinkedHashSet<>(base.passthrough());
        passthrough.addAll(override.passthrough());

        LinkedHashMap<String, FieldGroup> groups = new LinkedHashMap<>();
        for (FieldGroup group : base.groups()) {
            groups.put(group.groupKey(), group);
        }
        for (FieldGroup group : override.groups()) {
            groups.put(group.groupKey(), group);
        }

        LinkedHashMap<String, FieldDefinition> render = new LinkedHashMap<>();
        for (FieldDefinition field : base.render()) {
            render.put(field.rawKey(), field);
        }
        for (FieldDefinition field : override.render()) {
            render.put(field.rawKey(), field);
        }

        return new FieldOrchestration(
                ignore,
                passthrough,
                new ArrayList<>(groups.values()),
                new ArrayList<>(render.values()),
                mergePaginationBinding(base.pagination(), override.pagination()),
                mergeViewBinding(base.view(), override.view()),
                mergeActionsBinding(base.actions(), override.actions()),
                mergeFormBinding(base.form(), override.form())
        );
    }

    private PaginationBinding parsePaginationBinding(JsonNode node) {
        if (!node.isObject()) {
            return null;
        }
        return new PaginationBinding(
                defaultIfBlank(trimToNull(node.path("currentKey").asText(null)), "current"),
                defaultIfBlank(trimToNull(node.path("sizeKey").asText(null)), "size"),
                normalizePaginationRequestTarget(node.path("requestTarget").asText(null))
        );
    }

    private ViewBinding parseViewBinding(JsonNode node) {
        if (!node.isObject()) {
            return null;
        }
        return new ViewBinding(
                normalizeViewType(node.path("type").asText(null)),
                trimToNull(node.path("dataPath").asText(null))
        );
    }

    private ActionsBinding parseActionsBinding(JsonNode node) {
        if (!node.isObject()) {
            return null;
        }
        List<RowActionBinding> rowActions = new ArrayList<>();
        JsonNode rowActionsNode = node.path("rowActions");
        if (rowActionsNode.isArray()) {
            for (JsonNode actionNode : rowActionsNode) {
                String key = trimToNull(actionNode.path("key").asText(null));
                String label = trimToNull(actionNode.path("label").asText(null));
                String type = trimToNull(actionNode.path("type").asText(null));
                if (!StringUtils.hasText(key) || !StringUtils.hasText(label)) {
                    continue;
                }
                rowActions.add(new RowActionBinding(
                        key,
                        label,
                        defaultIfBlank(type, "action"),
                        trimToNull(actionNode.path("detailEndpointId").asText(null)),
                        trimToNull(actionNode.path("submitEndpointId").asText(null)),
                        trimToNull(actionNode.path("idField").asText(null)),
                        toObjectMap(actionNode.path("detailRequest"))
                ));
            }
        }
        return rowActions.isEmpty() ? null : new ActionsBinding(rowActions);
    }

    private FormBinding parseFormBinding(JsonNode node) {
        if (!node.isObject()) {
            return null;
        }
        List<FormFieldBinding> fields = new ArrayList<>();
        JsonNode fieldsNode = node.path("fields");
        if (fieldsNode.isArray()) {
            for (JsonNode fieldNode : fieldsNode) {
                String standardKey = trimToNull(fieldNode.path("standardKey").asText(null));
                String rawKey = trimToNull(fieldNode.path("rawKey").asText(null));
                String name = trimToNull(fieldNode.path("name").asText(null));
                String label = trimToNull(fieldNode.path("label").asText(null));
                String type = trimToNull(fieldNode.path("type").asText(null));
                if (!StringUtils.hasText(standardKey) && !StringUtils.hasText(rawKey) && !StringUtils.hasText(name)) {
                    continue;
                }
                fields.add(new FormFieldBinding(
                        name,
                        standardKey,
                        rawKey,
                        label,
                        defaultIfBlank(type, FIELD_TYPE_TEXT),
                        fieldNode.path("required").asBoolean(false),
                        fieldNode.path("readonly").asBoolean(false),
                        toObjectList(fieldNode.path("options"))
                ));
            }
        }
        if (fields.isEmpty()) {
            return null;
        }
        return new FormBinding(
                trimToNull(node.path("title").asText(null)),
                trimToNull(node.path("mode").asText(null)),
                trimToNull(node.path("submitLabel").asText(null)),
                fields,
                toObjectMap(node.path("submitAction"))
        );
    }

    private PaginationBinding mergePaginationBinding(PaginationBinding base, PaginationBinding override) {
        if (base == null && override == null) {
            return null;
        }
        PaginationBinding baseBinding = base != null ? base : PaginationBinding.defaultBinding();
        if (override == null) {
            return baseBinding;
        }
        return new PaginationBinding(
                defaultIfBlank(trimToNull(override.currentKey()), baseBinding.currentKey()),
                defaultIfBlank(trimToNull(override.sizeKey()), baseBinding.sizeKey()),
                defaultIfBlank(trimToNull(override.requestTarget()), baseBinding.requestTarget())
        );
    }

    private ViewBinding mergeViewBinding(ViewBinding base, ViewBinding override) {
        if (base == null && override == null) {
            return null;
        }
        if (base == null) {
            return override;
        }
        if (override == null) {
            return base;
        }
        return new ViewBinding(
                defaultIfBlank(trimToNull(override.type()), base.type()),
                defaultIfBlank(trimToNull(override.dataPath()), base.dataPath())
        );
    }

    private ActionsBinding mergeActionsBinding(ActionsBinding base, ActionsBinding override) {
        if (base == null) {
            return override;
        }
        if (override == null) {
            return base;
        }
        LinkedHashMap<String, RowActionBinding> actionMap = new LinkedHashMap<>();
        for (RowActionBinding action : base.rowActions()) {
            actionMap.put(action.key(), action);
        }
        for (RowActionBinding action : override.rowActions()) {
            actionMap.put(action.key(), action);
        }
        return new ActionsBinding(new ArrayList<>(actionMap.values()));
    }

    private FormBinding mergeFormBinding(FormBinding base, FormBinding override) {
        if (base == null) {
            return override;
        }
        if (override == null) {
            return base;
        }
        LinkedHashMap<String, FormFieldBinding> fieldMap = new LinkedHashMap<>();
        for (FormFieldBinding field : base.fields()) {
            fieldMap.put(field.identityKey(), field);
        }
        for (FormFieldBinding field : override.fields()) {
            fieldMap.put(field.identityKey(), field);
        }
        Map<String, Object> submitAction = override.submitAction() != null && !override.submitAction().isEmpty()
                ? override.submitAction()
                : base.submitAction();
        return new FormBinding(
                defaultIfBlank(trimToNull(override.title()), base.title()),
                defaultIfBlank(trimToNull(override.mode()), base.mode()),
                defaultIfBlank(trimToNull(override.submitLabel()), base.submitLabel()),
                new ArrayList<>(fieldMap.values()),
                submitAction
        );
    }

    private PaginationBinding resolveRuntimePaginationBinding(UiApiEndpoint endpoint, PaginationBinding configuredBinding) {
        PaginationBinding inferredBinding = inferDefaultPaginationBinding(endpoint);
        if (configuredBinding == null) {
            return inferredBinding;
        }
        return mergePaginationBinding(inferredBinding, configuredBinding);
    }

    private PaginationBinding inferDefaultPaginationBinding(UiApiEndpoint endpoint) {
        if (endpoint == null) {
            return PaginationBinding.defaultBinding();
        }
        boolean isListOperation = "list".equalsIgnoreCase(defaultIfBlank(endpoint.getOperationSafety(), ""));
        boolean isPostMethod = "POST".equalsIgnoreCase(defaultIfBlank(endpoint.getMethod(), ""));
        if (isListOperation && isPostMethod) {
            return new PaginationBinding("pageNo", "pageSize", PAGINATION_TARGET_BODY);
        }
        return PaginationBinding.defaultBinding();
    }

    private ViewBinding resolveViewBinding(
            UiApiEndpoint endpoint,
            ViewBinding configuredView,
            JsonNode responseNode,
            PrimaryArrayResult primaryArrayResult
    ) {
        String type = configuredView != null ? configuredView.type() : null;
        String dataPath = configuredView != null ? configuredView.dataPath() : null;

        if (!StringUtils.hasText(type)) {
            if ("list".equalsIgnoreCase(defaultIfBlank(endpoint.getOperationSafety(), "")) || primaryArrayResult != null) {
                type = VIEW_TYPE_LIST;
            } else if (resolveDefaultDetailNode(responseNode).isObject()) {
                type = VIEW_TYPE_DETAIL;
            } else {
                type = VIEW_TYPE_RAW;
            }
        }

        if (!StringUtils.hasText(dataPath)) {
            JsonNode dataNode = responseNode != null ? responseNode.path("data") : null;
            if (dataNode != null && !dataNode.isMissingNode() && !dataNode.isNull()) {
                dataPath = "$.data";
            } else {
                dataPath = JSON_ROOT;
            }
        }

        return new ViewBinding(type, dataPath);
    }

    private JsonNode resolveDetailNode(JsonNode responseNode, ViewBinding viewBinding) {
        if (viewBinding != null && StringUtils.hasText(viewBinding.dataPath())) {
            JsonNode configuredNode = extractJsonPath(responseNode, viewBinding.dataPath());
            if (configuredNode != null && !configuredNode.isMissingNode() && !configuredNode.isNull()) {
                if (configuredNode.isObject()) {
                    return configuredNode;
                }
                if (configuredNode.path("data").isObject()) {
                    return configuredNode.path("data");
                }
            }
        }
        return resolveDefaultDetailNode(responseNode);
    }

    private JsonNode resolveDefaultDetailNode(JsonNode responseNode) {
        if (responseNode == null || responseNode.isMissingNode() || responseNode.isNull()) {
            return responseNode;
        }
        JsonNode dataNode = responseNode.path("data");
        if (dataNode.isObject()) {
            return dataNode;
        }
        return responseNode;
    }

    private String normalizePaginationRequestTarget(String requestTarget) {
        if (!StringUtils.hasText(requestTarget)) {
            return PAGINATION_TARGET_QUERY;
        }
        String normalized = requestTarget.trim().toLowerCase(Locale.ROOT);
        if (PAGINATION_TARGET_BODY.equals(normalized)) {
            return PAGINATION_TARGET_BODY;
        }
        return PAGINATION_TARGET_QUERY;
    }

    private String normalizeViewType(String viewType) {
        if (!StringUtils.hasText(viewType)) {
            return null;
        }
        String normalized = viewType.trim().toLowerCase(Locale.ROOT);
        if (VIEW_TYPE_LIST.equals(normalized) || VIEW_TYPE_DETAIL.equals(normalized) || VIEW_TYPE_RAW.equals(normalized)) {
            return normalized;
        }
        return null;
    }

    private Set<String> toStringSet(JsonNode node) {
        LinkedHashSet<String> values = new LinkedHashSet<>();
        if (!node.isArray()) {
            return values;
        }
        for (JsonNode item : node) {
            if (item.isTextual() && StringUtils.hasText(item.asText())) {
                values.add(item.asText().trim());
            }
        }
        return values;
    }

    private List<FieldGroup> parseGroups(JsonNode groupsNode) {
        List<FieldGroup> groups = new ArrayList<>();
        if (!groupsNode.isArray()) {
            return groups;
        }
        for (JsonNode groupNode : groupsNode) {
            String groupKey = defaultIfBlank(groupNode.path("groupKey").asText(null), "group_" + groups.size());
            String label = defaultIfBlank(groupNode.path("label").asText(null), humanizeKey(groupKey));
            List<FieldDefinition> fields = parseFields(groupNode.path("fields"));
            groups.add(new FieldGroup(groupKey, label, fields));
        }
        return groups;
    }

    private List<FieldDefinition> parseFields(JsonNode node) {
        List<FieldDefinition> fields = new ArrayList<>();
        if (!node.isArray()) {
            return fields;
        }
        for (JsonNode item : node) {
            String rawKey = item.path("rawKey").asText(null);
            if (!StringUtils.hasText(rawKey)) {
                continue;
            }
            fields.add(new FieldDefinition(
                    rawKey.trim(),
                    trimToNull(item.path("standardKey").asText(null)),
                    trimToNull(item.path("label").asText(null)),
                    trimToNull(item.path("type").asText(null))
            ));
        }
        return fields;
    }

    private Map<String, String> loadAliasMap(String endpointId) {
        List<SemanticFieldAlias> aliases = semanticFieldAliasMapper.selectList(new LambdaQueryWrapper<SemanticFieldAlias>()
                .eq(SemanticFieldAlias::getApiId, endpointId));
        Map<String, String> aliasToStandardKey = new LinkedHashMap<>();
        for (SemanticFieldAlias alias : aliases) {
            if (StringUtils.hasText(alias.getAlias()) && StringUtils.hasText(alias.getStandardKey())) {
                aliasToStandardKey.put(alias.getAlias(), alias.getStandardKey());
            }
        }
        return aliasToStandardKey;
    }

    private Map<String, SemanticFieldDict> loadSemanticDictMap() {
        List<SemanticFieldDict> dicts = semanticFieldDictMapper.selectList(new LambdaQueryWrapper<SemanticFieldDict>()
                .eq(SemanticFieldDict::getIsActive, 1));
        Map<String, SemanticFieldDict> dictByKey = new LinkedHashMap<>();
        for (SemanticFieldDict dict : dicts) {
            dictByKey.put(dict.getStandardKey(), dict);
        }
        return dictByKey;
    }

    private Map<String, Map<String, String>> loadValueMap(String endpointId) {
        List<SemanticFieldValueMap> valueMaps = semanticFieldValueMapMapper.selectList(new LambdaQueryWrapper<SemanticFieldValueMap>()
                .and(wrapper -> wrapper.isNull(SemanticFieldValueMap::getApiId)
                        .or().eq(SemanticFieldValueMap::getApiId, "")
                        .or().eq(SemanticFieldValueMap::getApiId, endpointId))
                .orderByAsc(SemanticFieldValueMap::getSortOrder)
                .orderByAsc(SemanticFieldValueMap::getId));

        Map<String, Map<String, String>> result = new LinkedHashMap<>();
        for (SemanticFieldValueMap valueMap : valueMaps) {
            if (!StringUtils.hasText(valueMap.getApiId())) {
                result.computeIfAbsent(valueMap.getStandardKey(), key -> new LinkedHashMap<>())
                        .put(valueMap.getRawValue(), valueMap.getStandardValue());
            }
        }
        for (SemanticFieldValueMap valueMap : valueMaps) {
            if (Objects.equals(endpointId, valueMap.getApiId())) {
                result.computeIfAbsent(valueMap.getStandardKey(), key -> new LinkedHashMap<>())
                        .put(valueMap.getRawValue(), valueMap.getStandardValue());
            }
        }
        return result;
    }

    private Map<String, Map<String, String>> loadReverseValueMap(String endpointId) {
        List<SemanticFieldValueMap> valueMaps = semanticFieldValueMapMapper.selectList(new LambdaQueryWrapper<SemanticFieldValueMap>()
                .and(wrapper -> wrapper.isNull(SemanticFieldValueMap::getApiId)
                        .or().eq(SemanticFieldValueMap::getApiId, "")
                        .or().eq(SemanticFieldValueMap::getApiId, endpointId))
                .orderByAsc(SemanticFieldValueMap::getSortOrder)
                .orderByAsc(SemanticFieldValueMap::getId));

        Map<String, Map<String, String>> result = new LinkedHashMap<>();
        for (SemanticFieldValueMap valueMap : valueMaps) {
            if (!StringUtils.hasText(valueMap.getApiId())) {
                result.computeIfAbsent(valueMap.getStandardKey(), key -> new LinkedHashMap<>())
                        .put(valueMap.getStandardValue(), valueMap.getRawValue());
            }
        }
        for (SemanticFieldValueMap valueMap : valueMaps) {
            if (Objects.equals(endpointId, valueMap.getApiId())) {
                result.computeIfAbsent(valueMap.getStandardKey(), key -> new LinkedHashMap<>())
                        .put(valueMap.getStandardValue(), valueMap.getRawValue());
            }
        }
        return result;
    }

    private UiApiEndpoint requireEndpoint(String endpointId) {
        UiApiEndpoint endpoint = uiApiEndpointMapper.selectById(endpointId);
        if (endpoint == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "接口定义不存在: " + endpointId);
        }
        return endpoint;
    }

    private UiApiSource requireSource(String sourceId) {
        UiApiSource source = uiApiSourceMapper.selectById(sourceId);
        if (source == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "接口源不存在: " + sourceId);
        }
        return source;
    }

    private UiApiEndpointRole findRoleRelation(String endpointId, String roleId) {
        if (!StringUtils.hasText(roleId)) {
            return null;
        }
        return uiApiEndpointRoleMapper.selectOne(new LambdaQueryWrapper<UiApiEndpointRole>()
                .eq(UiApiEndpointRole::getEndpointId, endpointId)
                .eq(UiApiEndpointRole::getRoleId, roleId)
                .last("limit 1"));
    }

    private void validateRuntimeInvokeTarget(UiApiSource source, UiApiEndpoint endpoint) {
        if (!"active".equalsIgnoreCase(defaultIfBlank(source.getStatus(), "draft"))) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "接口源未启用，不能发起运行时调用");
        }
        if (!"active".equalsIgnoreCase(defaultIfBlank(endpoint.getStatus(), "inactive"))) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "接口定义未启用，不能发起运行时调用");
        }
        if (!StringUtils.hasText(source.getBaseUrl()) || !StringUtils.hasText(endpoint.getPath())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "接口基础地址或接口路径为空，不能发起运行时调用");
        }
    }

    private Object resolveInvokeBody(UiApiEndpoint endpoint, UiApiInvokeRequest request) {
        if (request != null && request.getBody() != null) {
            return request.getBody();
        }
        if (request != null && Boolean.FALSE.equals(request.getUseSampleWhenEmpty())) {
            return null;
        }
        return parsePossiblyJson(endpoint.getSampleRequest());
    }

    private UiApiFlowLog createFlowLog(
            String endpointId,
            String flowNum,
            String createdBy,
            String createdByName,
            UiHttpInvokeService.HttpExecutionResult result
    ) {
        UiApiFlowLog log = new UiApiFlowLog();
        log.setEndpointId(endpointId);
        log.setFlowNum(flowNum);
        log.setCreatedBy(createdBy);
        log.setCreatedByName(createdByName);
        log.setRequestUrl(result.requestUrl());
        log.setRequestHeaders(writeJson(result.requestHeaders()));
        log.setRequestQuery(writeJson(result.queryParams()));
        log.setRequestBody(writeJson(result.requestBody()));
        log.setResponseStatus(result.responseStatus());
        log.setResponseHeaders(writeJson(result.responseHeaders()));
        log.setResponseBody(writeJson(result.responseBody() != null ? parsePossiblyJson((String) result.responseBody()) : null));
        log.setInvokeStatus(result.success() ? "success" : "failed");
        log.setErrorMessage(result.errorMessage());
        uiApiFlowLogMapper.insert(log);
        return log;
    }

    private Object parsePossiblyJson(String raw) {
        if (!StringUtils.hasText(raw)) {
            return raw;
        }
        try {
            return objectMapper.readValue(raw, Object.class);
        } catch (Exception ex) {
            return raw;
        }
    }

    private String writeJson(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            return String.valueOf(value);
        }
    }

    private boolean isSelectField(String type) {
        return "select".equalsIgnoreCase(defaultIfBlank(type, ""));
    }

    private List<String> parseStandardValuesFromDict(SemanticFieldDict dict) {
        if (dict == null || !StringUtils.hasText(dict.getValueMap())) {
            return List.of();
        }
        try {
            Map<String, Object> valueMap = objectMapper.readValue(dict.getValueMap(), new TypeReference<LinkedHashMap<String, Object>>() {
            });
            LinkedHashSet<String> values = new LinkedHashSet<>();
            for (Object value : valueMap.values()) {
                if (value != null && StringUtils.hasText(String.valueOf(value))) {
                    values.add(String.valueOf(value));
                }
            }
            return new ArrayList<>(values);
        } catch (Exception ex) {
            return List.of();
        }
    }

    private Map<String, Object> safeCopyMap(Map<String, Object> source) {
        return source == null ? new LinkedHashMap<>() : new LinkedHashMap<>(source);
    }

    private Map<String, Object> safeCopyObjectMap(Object source) {
        if (source instanceof Map<?, ?> rawMap) {
            Map<String, Object> copy = new LinkedHashMap<>();
            for (Map.Entry<?, ?> entry : rawMap.entrySet()) {
                if (entry.getKey() == null) {
                    continue;
                }
                copy.put(String.valueOf(entry.getKey()), entry.getValue());
            }
            return copy;
        }
        return new LinkedHashMap<>();
    }

    private Map<String, Object> toObjectMap(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull() || !node.isObject()) {
            return new LinkedHashMap<>();
        }
        try {
            return objectMapper.convertValue(node, new TypeReference<LinkedHashMap<String, Object>>() {
            });
        } catch (IllegalArgumentException ex) {
            return new LinkedHashMap<>();
        }
    }

    private List<Map<String, Object>> toObjectList(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull() || !node.isArray()) {
            return new ArrayList<>();
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (JsonNode item : node) {
            result.add(toObjectMap(item));
        }
        return result;
    }

    private boolean isIgnoredField(Set<String> ignore, String fieldName, String dataPath) {
        if (ignore == null || ignore.isEmpty()) {
            return false;
        }
        return ignore.contains(fieldName) || ignore.contains(buildChildPath(dataPath, fieldName));
    }

    private String buildChildPath(String parentPath, String fieldName) {
        if (!StringUtils.hasText(parentPath) || JSON_ROOT.equals(parentPath)) {
            return fieldName;
        }
        if (parentPath.endsWith(".")) {
            return parentPath + fieldName;
        }
        return parentPath + "." + fieldName;
    }

    private Object resolveFormInitialValue(
            FormFieldBinding field,
            JsonNode detailNode,
            Map<String, String> aliasToStandardKey,
            Map<String, Map<String, String>> semanticValueMapByKey
    ) {
        if (field == null || detailNode == null || detailNode.isMissingNode() || detailNode.isNull()) {
            return null;
        }
        JsonNode valueNode = null;
        if (StringUtils.hasText(field.rawKey())) {
            valueNode = extractJsonPath(detailNode, field.rawKey());
        }
        if ((valueNode == null || valueNode.isMissingNode() || valueNode.isNull()) && StringUtils.hasText(field.name())) {
            valueNode = detailNode.path(field.name());
        }
        if ((valueNode == null || valueNode.isMissingNode() || valueNode.isNull()) && StringUtils.hasText(field.standardKey())) {
            String rawFieldName = resolveRawFieldNameByStandardKey(detailNode, field.standardKey(), aliasToStandardKey);
            if (StringUtils.hasText(rawFieldName)) {
                valueNode = detailNode.path(rawFieldName);
            }
        }
        if (valueNode == null || valueNode.isMissingNode() || valueNode.isNull()) {
            return null;
        }
        if (valueNode.isNumber()) {
            return valueNode.numberValue();
        }
        if (valueNode.isBoolean()) {
            return valueNode.booleanValue();
        }
        return normalizeDisplayValue(valueNode, field.standardKey(), semanticValueMapByKey);
    }

    private String resolveRawFieldNameByStandardKey(JsonNode detailNode, String standardKey, Map<String, String> aliasToStandardKey) {
        if (!StringUtils.hasText(standardKey) || detailNode == null || !detailNode.isObject()) {
            return null;
        }
        var fieldNames = detailNode.fieldNames();
        while (fieldNames.hasNext()) {
            String fieldName = fieldNames.next();
            String resolvedStandardKey = resolveStandardKey(fieldName, aliasToStandardKey);
            if (Objects.equals(standardKey, resolvedStandardKey) || Objects.equals(standardKey, fieldName)) {
                return fieldName;
            }
        }
        return null;
    }

    private JsonNode extractJsonPath(JsonNode root, String jsonPath) {
        if (!StringUtils.hasText(jsonPath) || JSON_ROOT.equals(jsonPath.trim())) {
            return root;
        }
        String normalized = jsonPath.trim();
        if (normalized.startsWith(JSON_ROOT_DOT)) {
            normalized = normalized.substring(2);
        } else if (normalized.startsWith(JSON_ROOT)) {
            normalized = normalized.substring(1);
        }
        if (!StringUtils.hasText(normalized)) {
            return root;
        }

        JsonNode current = root;
        for (String token : normalized.split("\\.")) {
            if (current == null || current.isMissingNode()) {
                return null;
            }
            if (token.endsWith("[*]") || token.endsWith("[]")) {
                String fieldName = token.substring(0, token.length() - 3);
                current = current.path(fieldName);
                continue;
            }
            Matcher matcher = ARRAY_SEGMENT_PATTERN.matcher(token);
            if (matcher.matches()) {
                current = current.path(matcher.group(1));
                current = current.path(Integer.parseInt(matcher.group(2)));
            } else {
                current = current.path(token);
            }
        }
        return current;
    }

    private PrimaryArrayResult findPrimaryArrayResult(JsonNode root) {
        if (root == null || root.isMissingNode() || root.isNull()) {
            return null;
        }
        if (root.isArray()) {
            return new PrimaryArrayResult(root, null, "root");
        }
        if (!root.isObject()) {
            return null;
        }
        for (String key : PRIMARY_ARRAY_CANDIDATE_KEYS) {
            JsonNode candidate = root.path(key);
            if (candidate.isArray()) {
                return new PrimaryArrayResult(candidate, root, key);
            }
        }

        for (String wrapperKey : PRIMARY_ARRAY_CANDIDATE_KEYS) {
            JsonNode wrapper = root.path(wrapperKey);
            PrimaryArrayResult nested = findPrimaryArrayResult(wrapper);
            if (nested != null) {
                return nested;
            }
        }

        var fieldNames = root.fieldNames();
        while (fieldNames.hasNext()) {
            String key = fieldNames.next();
            JsonNode candidate = root.path(key);
            if (candidate.isArray()) {
                return new PrimaryArrayResult(candidate, root, key);
            }
        }
        fieldNames = root.fieldNames();
        while (fieldNames.hasNext()) {
            String key = fieldNames.next();
            PrimaryArrayResult nested = findPrimaryArrayResult(root.path(key));
            if (nested != null) {
                return nested;
            }
        }
        return null;
    }

    private String resolveStandardKey(String rawKey, Map<String, String> aliasToStandardKey) {
        String direct = aliasToStandardKey.get(rawKey);
        if (StringUtils.hasText(direct)) {
            return direct;
        }
        String lastSegment = rawKey.contains(".") ? rawKey.substring(rawKey.lastIndexOf('.') + 1) : rawKey;
        lastSegment = lastSegment.replace("[]", "");
        return aliasToStandardKey.get(lastSegment);
    }

    private String resolveFieldLabel(String rawKey, Map<String, String> aliasToStandardKey, Map<String, SemanticFieldDict> semanticDictByKey) {
        String standardKey = resolveStandardKey(rawKey, aliasToStandardKey);
        SemanticFieldDict dict = semanticDictByKey.get(standardKey);
        return dict != null && StringUtils.hasText(dict.getLabel()) ? dict.getLabel() : humanizeKey(rawKey);
    }

    private String normalizeDisplayValue(JsonNode valueNode, String standardKey, Map<String, Map<String, String>> semanticValueMapByKey) {
        if (valueNode == null || valueNode.isNull() || valueNode.isMissingNode()) {
            return DISPLAY_NULL;
        }
        if (valueNode.isTextual() || valueNode.isNumber() || valueNode.isBoolean()) {
            String rawValue = valueNode.asText();
            if (StringUtils.hasText(standardKey)) {
                String mapped = semanticValueMapByKey.getOrDefault(standardKey, Map.of()).get(rawValue);
                if (StringUtils.hasText(mapped)) {
                    return mapped;
                }
            }
            return rawValue;
        }
        if (valueNode.isArray()) {
            List<String> items = new ArrayList<>();
            for (JsonNode item : valueNode) {
                items.add(normalizeDisplayValue(item, standardKey, semanticValueMapByKey));
            }
            return String.join(", ", items);
        }
        return stringifyNode(valueNode);
    }

    private String stringifyNode(JsonNode node) {
        try {
            Object value = objectMapper.treeToValue(node, Object.class);
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            return String.valueOf(node);
        }
    }

    private String inferFieldType(JsonNode node) {
        if (node == null || node.isNull()) {
            return FIELD_TYPE_TEXT;
        }
        if (node.isNumber()) {
            return FIELD_TYPE_NUMBER;
        }
        if (node.isBoolean()) {
            return FIELD_TYPE_BOOLEAN;
        }
        return FIELD_TYPE_TEXT;
    }

    private String humanizeKey(String rawKey) {
        String lastSegment = rawKey.contains(".") ? rawKey.substring(rawKey.lastIndexOf('.') + 1) : rawKey;
        String normalized = lastSegment.replace("[]", "");
        normalized = normalized.replaceAll("([a-z0-9])([A-Z])", "$1 $2");
        normalized = normalized.replace('_', ' ').replace('-', ' ');
        normalized = normalized.trim().replaceAll("\\s+", " ");
        if (!StringUtils.hasText(normalized)) {
            return rawKey;
        }
        return normalized.substring(0, 1).toUpperCase(Locale.ROOT) + normalized.substring(1);
    }

    private String buildSubtitle(UiApiEndpoint endpoint, UiApiEndpointRole roleRelation) {
        String summary = defaultIfBlank(endpoint.getSummary(), endpoint.getPath());
        if (Objects.equals(summary, endpoint.getName())) {
            summary = null;
        }
        if (roleRelation != null && StringUtils.hasText(roleRelation.getRoleName())) {
            return StringUtils.hasText(summary) ? summary + ROLE_PREFIX + roleRelation.getRoleName() : roleRelation.getRoleName();
        }
        return summary;
    }

    private Map<String, Object> element(String type, Map<String, Object> props, List<String> children) {
        return mapOf(
                PROP_TYPE, type,
                PROP_PROPS, props,
                PROP_CHILDREN, children
        );
    }

    private Map<String, Object> mapOf(Object... values) {
        Map<String, Object> map = new LinkedHashMap<>();
        for (int i = 0; i < values.length; i += 2) {
            map.put(String.valueOf(values[i]), values[i + 1]);
        }
        return map;
    }

    private String nextId(String prefix, AtomicInteger sequence) {
        return prefix + sequence.getAndIncrement();
    }

    private String trimToNull(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        return value.trim();
    }

    private String defaultIfBlank(String value, String defaultValue) {
        return StringUtils.hasText(value) ? value : defaultValue;
    }

    private record FieldOrchestration(
            Set<String> ignore,
            Set<String> passthrough,
            List<FieldGroup> groups,
            List<FieldDefinition> render,
            PaginationBinding pagination,
            ViewBinding view,
            ActionsBinding actions,
            FormBinding form
    ) {
        private static FieldOrchestration empty() {
            return new FieldOrchestration(
                    new LinkedHashSet<>(),
                    new LinkedHashSet<>(),
                    new ArrayList<>(),
                    new ArrayList<>(),
                    null,
                    null,
                    null,
                    null
            );
        }
    }

    private record PaginationBinding(String currentKey, String sizeKey, String requestTarget) {
        private static PaginationBinding defaultBinding() {
            return new PaginationBinding("current", "size", PAGINATION_TARGET_QUERY);
        }
    }

    private record ViewBinding(String type, String dataPath) {
    }

    private record ActionsBinding(List<RowActionBinding> rowActions) {
    }

    private record RowActionBinding(
            String key,
            String label,
            String type,
            String detailEndpointId,
            String submitEndpointId,
            String idField,
            Map<String, Object> detailRequest
    ) {
        private Map<String, Object> toMap() {
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("key", key);
            result.put("label", label);
            result.put("type", type);
            if (StringUtils.hasText(detailEndpointId)) {
                result.put("detailEndpointId", detailEndpointId);
            }
            if (StringUtils.hasText(submitEndpointId)) {
                result.put("submitEndpointId", submitEndpointId);
            }
            if (StringUtils.hasText(idField)) {
                result.put("idField", idField);
            }
            if (detailRequest != null && !detailRequest.isEmpty()) {
                result.put("detailRequest", detailRequest);
            }
            return result;
        }
    }

    private record FieldGroup(String groupKey, String label, List<FieldDefinition> fields) {
    }

    private record FieldDefinition(String rawKey, String standardKey, String label, String type) {
    }

    private record FormBinding(
            String title,
            String mode,
            String submitLabel,
            List<FormFieldBinding> fields,
            Map<String, Object> submitAction
    ) {
    }

    private record FormFieldBinding(
            String name,
            String standardKey,
            String rawKey,
            String label,
            String type,
            boolean required,
            boolean readonly,
            List<Map<String, Object>> options
    ) {
        private String identityKey() {
            return defaultIdentity(name, standardKey, rawKey);
        }

        private Map<String, Object> toMap(List<Map<String, Object>> resolvedOptions) {
            Map<String, Object> result = new LinkedHashMap<>();
            String resolvedName = defaultIdentity(name, standardKey, rawKey);
            if (StringUtils.hasText(resolvedName)) {
                result.put("name", resolvedName);
            }
            if (StringUtils.hasText(label)) {
                result.put("label", label);
            }
            if (StringUtils.hasText(type)) {
                result.put("type", type);
            }
            if (required) {
                result.put("required", true);
            }
            if (readonly) {
                result.put("readonly", true);
            }
            if (resolvedOptions != null && !resolvedOptions.isEmpty()) {
                result.put("options", resolvedOptions);
            }
            if (StringUtils.hasText(standardKey)) {
                result.put("standardKey", standardKey);
            }
            if (StringUtils.hasText(rawKey)) {
                result.put("rawKey", rawKey);
            }
            return result;
        }

        private static String defaultIdentity(String name, String standardKey, String rawKey) {
            if (StringUtils.hasText(name)) {
                return name;
            }
            if (StringUtils.hasText(standardKey)) {
                return standardKey;
            }
            return rawKey;
        }
    }

    private record ResolvedField(
            String rawKey,
            String standardKey,
            String label,
            String type,
            JsonNode rawNode,
            String displayValue
    ) {
        private boolean isMetricCandidate() {
            return rawNode != null
                    && !rawNode.isArray()
                    && !rawNode.isObject()
                    && (FIELD_TYPE_NUMBER.equalsIgnoreCase(type) || rawNode.isNumber());
        }

        private Object metricValue() {
            if (rawNode == null || rawNode.isNull()) {
                return 0;
            }
            if (rawNode.isIntegralNumber()) {
                return rawNode.asLong();
            }
            if (rawNode.isNumber()) {
                return rawNode.asDouble();
            }
            return displayValue;
        }

        private String metricFormat() {
            return rawNode != null && rawNode.isNumber() ? FIELD_TYPE_NUMBER : FIELD_TYPE_TEXT;
        }
    }

    private record PrimaryArrayResult(
            JsonNode arrayNode,
            JsonNode containerNode,
            String arrayKey
    ) {
    }
}
