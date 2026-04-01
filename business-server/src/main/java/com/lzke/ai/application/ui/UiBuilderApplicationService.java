package com.lzke.ai.application.ui;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.lzke.ai.application.dto.PageQuery;
import com.lzke.ai.application.dto.UiApiEndpointRequest;
import com.lzke.ai.application.dto.UiApiSourceRequest;
import com.lzke.ai.application.dto.UiApiTestRequest;
import com.lzke.ai.application.dto.UiApiTestResponse;
import com.lzke.ai.application.dto.UiBuilderAuthTypeResponse;
import com.lzke.ai.application.dto.UiBuilderPageDetailResponse;
import com.lzke.ai.application.dto.UiBuilderNodeTypeResponse;
import com.lzke.ai.application.dto.UiBuilderOverviewResponse;
import com.lzke.ai.application.dto.UiNodeBindingRequest;
import com.lzke.ai.application.dto.UiOpenApiImportRequest;
import com.lzke.ai.application.dto.UiPageNodeRequest;
import com.lzke.ai.application.dto.UiPagePreviewResponse;
import com.lzke.ai.application.dto.UiPageRequest;
import com.lzke.ai.application.dto.UiProjectRequest;
import com.lzke.ai.domain.entity.UiApiEndpoint;
import com.lzke.ai.domain.entity.UiApiSource;
import com.lzke.ai.domain.entity.UiApiTag;
import com.lzke.ai.domain.entity.UiApiTestLog;
import com.lzke.ai.domain.entity.UiNodeBinding;
import com.lzke.ai.domain.entity.UiPage;
import com.lzke.ai.domain.entity.UiPageNode;
import com.lzke.ai.domain.entity.UiProject;
import com.lzke.ai.domain.entity.UiSpecVersion;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiEndpointMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiSourceMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiTagMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiTestLogMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiNodeBindingMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiPageMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiPageNodeMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiProjectMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiSpecVersionMapper;
import com.lzke.ai.interfaces.dto.PageResult;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import java.util.Comparator;
import java.util.Iterator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * UI Builder 应用服务。
 *
 * <p>该服务是 UI Builder 模块的“流程编排层”，负责串起以下运行时能力：
 *
 * <ul>
 *     <li>接口源、接口定义、页面、节点、字段绑定的增删改查</li>
 *     <li>OpenAPI 文档导入与接口标准化</li>
 *     <li>接口联调与联调日志记录</li>
 *     <li>页面配置到 json-render spec 的转换与发布</li>
 * </ul>
 *
 * <p>从本次重构开始，静态说明性对象（节点类型、表结构说明、模块流程等）
 * 不再由当前类直接组装，而是统一委托给 {@link UiBuilderMetadataService}。
 */
@Service
@RequiredArgsConstructor
public class UiBuilderApplicationService {

    private static final Set<String> OPEN_API_METHODS = Set.of("get", "post", "put", "delete", "patch");
    private static final Pattern ARRAY_SEGMENT_PATTERN = Pattern.compile("([A-Za-z0-9_\\-]+)\\[(\\d+)]");

    private final ObjectMapper objectMapper;
    private final RestTemplate restTemplate;
    private final UiBuilderMetadataService uiBuilderMetadataService;
    private final UiApiSourceMapper uiApiSourceMapper;
    private final UiApiTagMapper uiApiTagMapper;
    private final UiApiEndpointMapper uiApiEndpointMapper;
    private final UiApiTestLogMapper uiApiTestLogMapper;
    private final UiProjectMapper uiProjectMapper;
    private final UiPageMapper uiPageMapper;
    private final UiPageNodeMapper uiPageNodeMapper;
    private final UiNodeBindingMapper uiNodeBindingMapper;
    private final UiSpecVersionMapper uiSpecVersionMapper;

    /**
     * 返回 UI Builder 的概览说明。
     *
     * @return 页面概览所需的静态元数据
     */
    public UiBuilderOverviewResponse getOverview() {
        return uiBuilderMetadataService.buildOverview();
    }

    /**
     * 获取当前前端可消费的节点类型列表。
     *
     * @return 节点类型定义
     */
    public List<UiBuilderNodeTypeResponse> getNodeTypes() {
        return uiBuilderMetadataService.nodeTypes();
    }

    /**
     * 分页返回当前前端可消费的节点类型列表。
     *
     * <p>节点类型属于静态元数据，不需要走数据库分页，因此这里采用
     * 内存分页的方式包装成统一的 {@link PageResult}，以便前端在
     * `UiBuilderController` 下所有列表接口上保持一致的数据结构。
     *
     * @param query 分页参数
     * @return 分页节点类型定义
     */
    public PageResult<UiBuilderNodeTypeResponse> getNodeTypes(PageQuery query) {
        return paginateList(getNodeTypes(), query);
    }

    /**
     * 获取当前支持的认证方式列表。
     *
     * @return 认证方式定义
     */
    public List<UiBuilderAuthTypeResponse> getAuthTypes() {
        return uiBuilderMetadataService.authTypes();
    }

    /**
     * 分页返回当前支持的认证方式列表。
     *
     * <p>认证方式同样属于静态说明性元数据，因此采用内存分页包装，
     * 保持与其他列表接口一致的返回协议。
     *
     * @param query 分页参数
     * @return 分页认证方式定义
     */
    public PageResult<UiBuilderAuthTypeResponse> getAuthTypes(PageQuery query) {
        return paginateList(getAuthTypes(), query);
    }

    /**
     * 按更新时间倒序查询接口源。
     *
     * @return 接口源列表
     */
    public List<UiApiSource> listSources() {
        return uiApiSourceMapper.selectList(new LambdaQueryWrapper<UiApiSource>()
                .orderByDesc(UiApiSource::getUpdatedAt)
                .orderByDesc(UiApiSource::getCreatedAt));
    }

    /**
     * 分页查询接口源列表。
     *
     * @param query 分页参数
     * @return 分页后的接口源列表
     */
    public PageResult<UiApiSource> listSources(PageQuery query) {
        Page<UiApiSource> pageParam = buildPage(query);
        Page<UiApiSource> result = uiApiSourceMapper.selectPage(pageParam, new LambdaQueryWrapper<UiApiSource>()
                .orderByDesc(UiApiSource::getUpdatedAt)
                .orderByDesc(UiApiSource::getCreatedAt));
        return PageResult.of(result.getRecords(), result.getTotal(), query.getPage(), query.getSize());
    }

    /**
     * 查询接口源下的标签列表。
     *
     * @param sourceId 接口源 ID
     * @return 标签列表
     */
    public List<UiApiTag> listTagsBySource(String sourceId) {
        requireSource(sourceId);
        return uiApiTagMapper.selectList(new LambdaQueryWrapper<UiApiTag>()
                .eq(UiApiTag::getSourceId, sourceId)
                .orderByAsc(UiApiTag::getName)
                .orderByAsc(UiApiTag::getCreatedAt));
    }

    /**
     * 分页查询接口源下的标签列表。
     *
     * @param sourceId 接口源 ID
     * @param query 分页参数
     * @return 分页后的标签列表
     */
    public PageResult<UiApiTag> listTagsBySource(String sourceId, PageQuery query) {
        requireSource(sourceId);
        Page<UiApiTag> pageParam = buildPage(query);
        Page<UiApiTag> result = uiApiTagMapper.selectPage(pageParam, new LambdaQueryWrapper<UiApiTag>()
                .eq(UiApiTag::getSourceId, sourceId)
                .orderByAsc(UiApiTag::getName)
                .orderByAsc(UiApiTag::getCreatedAt));
        return PageResult.of(result.getRecords(), result.getTotal(), query.getPage(), query.getSize());
    }

    /**
     * 创建接口源。
     *
     * @param request 接口源创建请求
     * @return 持久化后的接口源
     */
    @Transactional
    public UiApiSource createSource(UiApiSourceRequest request) {
        validateSourceRequest(request, false);
        ensureSourceCodeUnique(request.getCode(), null);

        UiApiSource source = new UiApiSource();
        applySourceRequest(source, request);
        uiApiSourceMapper.insert(source);
        return source;
    }

    /**
     * 更新接口源。
     *
     * @param sourceId 接口源 ID
     * @param request 接口源更新请求
     * @return 更新后的接口源
     */
    @Transactional
    public UiApiSource updateSource(String sourceId, UiApiSourceRequest request) {
        validateSourceRequest(request, true);
        UiApiSource source = requireSource(sourceId);
        ensureSourceCodeUnique(request.getCode(), sourceId);
        applySourceRequest(source, request);
        uiApiSourceMapper.updateById(source);
        return source;
    }

    /**
     * 删除接口源及其下游接口定义、联调日志。
     *
     * @param sourceId 接口源 ID
     */
    @Transactional
    public void deleteSource(String sourceId) {
        requireSource(sourceId);
        List<UiApiEndpoint> endpoints = listEndpointsBySource(sourceId);
        List<String> endpointIds = endpoints.stream().map(UiApiEndpoint::getId).toList();
        if (!endpointIds.isEmpty()) {
            uiApiTestLogMapper.delete(new LambdaQueryWrapper<UiApiTestLog>().in(UiApiTestLog::getEndpointId, endpointIds));
            uiApiEndpointMapper.delete(new LambdaQueryWrapper<UiApiEndpoint>().in(UiApiEndpoint::getId, endpointIds));
        }
        uiApiTagMapper.delete(new LambdaQueryWrapper<UiApiTag>().eq(UiApiTag::getSourceId, sourceId));
        uiApiSourceMapper.deleteById(sourceId);
    }

    /**
     * 查询某个接口源下的接口定义。
     *
     * @param sourceId 接口源 ID
     * @return 接口定义列表
     */
    public List<UiApiEndpoint> listEndpointsBySource(String sourceId) {
        requireSource(sourceId);
        List<UiApiEndpoint> endpoints = uiApiEndpointMapper.selectList(new LambdaQueryWrapper<UiApiEndpoint>()
                .eq(UiApiEndpoint::getSourceId, sourceId)
                .orderByAsc(UiApiEndpoint::getPath)
                .orderByAsc(UiApiEndpoint::getMethod));
        attachTagNames(endpoints, sourceId);
        return endpoints;
    }

    /**
     * 分页查询某个接口源下的接口定义。
     *
     * <p>为了兼容前端的标签筛选，这里额外支持按 `tagId` 精确筛选，
     * 以及按“未分组接口”进行条件分页。
     *
     * @param sourceId 接口源 ID
     * @param query 分页参数
     * @param tagId 标签 ID，可为空
     * @param untagged 是否仅查询未分组接口
     * @return 分页后的接口定义列表
     */
    public PageResult<UiApiEndpoint> listEndpointsBySource(String sourceId, PageQuery query, String tagId, Boolean untagged) {
        requireSource(sourceId);
        LambdaQueryWrapper<UiApiEndpoint> wrapper = new LambdaQueryWrapper<UiApiEndpoint>()
                .eq(UiApiEndpoint::getSourceId, sourceId)
                .orderByAsc(UiApiEndpoint::getPath)
                .orderByAsc(UiApiEndpoint::getMethod);
        if (Boolean.TRUE.equals(untagged)) {
            wrapper.and(condition -> condition.isNull(UiApiEndpoint::getTagId).or().eq(UiApiEndpoint::getTagId, ""));
        } else if (StringUtils.hasText(tagId)) {
            wrapper.eq(UiApiEndpoint::getTagId, tagId);
        }

        Page<UiApiEndpoint> pageParam = buildPage(query);
        Page<UiApiEndpoint> result = uiApiEndpointMapper.selectPage(pageParam, wrapper);
        attachTagNames(result.getRecords(), sourceId);
        return PageResult.of(result.getRecords(), result.getTotal(), query.getPage(), query.getSize());
    }

    /**
     * 获取单个接口定义详情。
     *
     * @param endpointId 接口定义 ID
     * @return 接口定义
     */
    public UiApiEndpoint getEndpoint(String endpointId) {
        UiApiEndpoint endpoint = requireEndpoint(endpointId);
        attachTagNames(List.of(endpoint), endpoint.getSourceId());
        return endpoint;
    }

    /**
     * 查询接口联调日志。
     *
     * <p>默认只返回最近 20 条，便于前端快速查看最近几次联调结果。
     *
     * @param endpointId 接口定义 ID
     * @return 联调日志列表
     */
    public List<UiApiTestLog> listTestLogs(String endpointId) {
        requireEndpoint(endpointId);
        return uiApiTestLogMapper.selectList(new LambdaQueryWrapper<UiApiTestLog>()
                .eq(UiApiTestLog::getEndpointId, endpointId)
                .orderByDesc(UiApiTestLog::getCreatedAt)
                .last("limit 20"));
    }

    /**
     * 分页查询接口联调日志。
     *
     * <p>分页接口不再通过 SQL `limit 20` 写死条数，而是统一使用
     * {@link PageQuery} 中的分页参数。当前前端默认会请求第一页、每页 20 条。
     *
     * @param endpointId 接口定义 ID
     * @param query 分页参数
     * @return 分页联调日志
     */
    public PageResult<UiApiTestLog> listTestLogs(String endpointId, PageQuery query) {
        requireEndpoint(endpointId);
        Page<UiApiTestLog> pageParam = buildPage(query);
        Page<UiApiTestLog> result = uiApiTestLogMapper.selectPage(pageParam, new LambdaQueryWrapper<UiApiTestLog>()
                .eq(UiApiTestLog::getEndpointId, endpointId)
                .orderByDesc(UiApiTestLog::getCreatedAt));
        return PageResult.of(result.getRecords(), result.getTotal(), query.getPage(), query.getSize());
    }

    /**
     * 创建接口定义。
     *
     * @param request 接口定义请求
     * @return 持久化后的接口定义
     */
    @Transactional
    public UiApiEndpoint createEndpoint(UiApiEndpointRequest request) {
        validateEndpointRequest(request, false);
        requireSource(request.getSourceId());
        if (StringUtils.hasText(request.getTagId())) {
            requireTagInSource(request.getTagId(), request.getSourceId());
        }
        UiApiEndpoint endpoint = new UiApiEndpoint();
        applyEndpointRequest(endpoint, request);
        uiApiEndpointMapper.insert(endpoint);
        attachTagNames(List.of(endpoint), endpoint.getSourceId());
        return endpoint;
    }

    /**
     * 更新接口定义。
     *
     * @param endpointId 接口定义 ID
     * @param request 更新请求
     * @return 更新后的接口定义
     */
    @Transactional
    public UiApiEndpoint updateEndpoint(String endpointId, UiApiEndpointRequest request) {
        validateEndpointRequest(request, true);
        UiApiEndpoint endpoint = requireEndpoint(endpointId);
        if (StringUtils.hasText(request.getSourceId())) {
            requireSource(request.getSourceId());
        }
        if (StringUtils.hasText(request.getTagId())) {
            requireTagInSource(request.getTagId(), defaultIfBlank(request.getSourceId(), endpoint.getSourceId()));
        }
        applyEndpointRequest(endpoint, request);
        uiApiEndpointMapper.updateById(endpoint);
        attachTagNames(List.of(endpoint), endpoint.getSourceId());
        return endpoint;
    }

    /**
     * 删除接口定义及其联调日志。
     *
     * @param endpointId 接口定义 ID
     */
    @Transactional
    public void deleteEndpoint(String endpointId) {
        requireEndpoint(endpointId);
        uiApiTestLogMapper.delete(new LambdaQueryWrapper<UiApiTestLog>().eq(UiApiTestLog::getEndpointId, endpointId));
        uiApiEndpointMapper.deleteById(endpointId);
    }

    /**
     * 导入 OpenAPI/Swagger 文档并标准化为接口定义。
     *
     * <p>当前支持三种输入顺序：
     *
     * <ol>
     *     <li>优先使用请求体中的 document 文本</li>
     *     <li>否则尝试请求体中的 documentUrl</li>
     *     <li>再否则回退到接口源上配置的 docUrl</li>
     * </ol>
     *
     * <p>导入时会遍历 `paths` 下的标准 HTTP 方法，并将请求/响应 schema 和样例提取出来，
     * 已存在的 method + path 会执行覆盖更新，不会重复插入。
     *
     * @param sourceId 接口源 ID
     * @param request OpenAPI 导入请求
     * @return 导入或更新后的接口定义列表
     */
    @Transactional
    public List<UiApiEndpoint> importOpenApi(String sourceId, UiOpenApiImportRequest request) {
        UiApiSource source = requireSource(sourceId);
        String document = loadOpenApiDocument(source, request);
        JsonNode rootNode = readJsonTree(document, "OpenAPI 文档解析失败");
        JsonNode pathsNode = rootNode.path("paths");
        if (!pathsNode.isObject() || pathsNode.isEmpty()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "OpenAPI paths 节点为空");
        }

        List<UiApiEndpoint> imported = new ArrayList<>();
        Iterator<Map.Entry<String, JsonNode>> pathIterator = pathsNode.fields();
        while (pathIterator.hasNext()) {
            Map.Entry<String, JsonNode> pathEntry = pathIterator.next();
            String path = pathEntry.getKey();
            JsonNode pathConfig = pathEntry.getValue();
            Iterator<Map.Entry<String, JsonNode>> methodIterator = pathConfig.fields();
            while (methodIterator.hasNext()) {
                Map.Entry<String, JsonNode> methodEntry = methodIterator.next();
                String method = methodEntry.getKey().toLowerCase(Locale.ROOT);
                if (!OPEN_API_METHODS.contains(method)) {
                    continue;
                }
                JsonNode operationNode = methodEntry.getValue();
                UiApiEndpoint endpoint = findEndpointBySourceAndMethodPath(sourceId, method.toUpperCase(Locale.ROOT), path);
                if (endpoint == null) {
                    endpoint = new UiApiEndpoint();
                    endpoint.setSourceId(source.getId());
                }
                String summary = operationNode.path("summary").asText(null);
                endpoint.setTagId(resolveTagId(sourceId, operationNode));
                endpoint.setMethod(method.toUpperCase(Locale.ROOT));
                endpoint.setPath(path);
                endpoint.setName(firstNonBlank(summary, endpoint.getMethod() + " " + path));
                endpoint.setSummary(summary);
                endpoint.setRequestContentType(extractRequestContentType(operationNode));
                endpoint.setRequestSchema(toJsonString(extractRequestSchema(rootNode, operationNode)));
                endpoint.setResponseSchema(toJsonString(extractResponseSchema(rootNode, operationNode)));
                endpoint.setSampleRequest(toJsonString(extractRequestExample(rootNode, operationNode)));
                endpoint.setSampleResponse(toJsonString(extractResponseExample(rootNode, operationNode)));
                endpoint.setStatus("active");

                if (StringUtils.hasText(endpoint.getId())) {
                    uiApiEndpointMapper.updateById(endpoint);
                } else {
                    uiApiEndpointMapper.insert(endpoint);
                }
                imported.add(endpoint);
            }
        }
        attachTagNames(imported, sourceId);
        return imported;
    }

    /**
     * 导入 OpenAPI/Swagger 文档后，以分页格式返回本次导入结果。
     *
     * <p>导入本身仍然复用全量导入逻辑，分页只作用在返回给前端的结果切片，
     * 方便前端在单次导入接口较多时依然维持一致的列表展示协议。
     *
     * @param sourceId 接口源 ID
     * @param request OpenAPI 导入请求
     * @param query 分页参数
     * @return 分页后的本次导入结果
     */
    @Transactional
    public PageResult<UiApiEndpoint> importOpenApi(String sourceId, UiOpenApiImportRequest request, PageQuery query) {
        return paginateList(importOpenApi(sourceId, request), query);
    }

    /**
     * 发起一次接口联调，并记录联调日志。
     *
     * <p>联调会根据接口源上的认证配置自动拼装请求头和 Query 参数，
     * 然后把请求/响应快照写入 `ui_api_test_logs`，供后续字段绑定和问题排查使用。
     *
     * @param endpointId 接口定义 ID
     * @param request 联调请求
     * @return 联调结果
     */
    @Transactional
    public UiApiTestResponse testEndpoint(String endpointId, UiApiTestRequest request) {
        UiApiEndpoint endpoint = requireEndpoint(endpointId);
        UiApiSource source = requireSource(endpoint.getSourceId());

        String requestUrl = buildRequestUrl(source, endpoint, request != null ? request.getQueryParams() : null);
        HttpMethod httpMethod = HttpMethod.valueOf(endpoint.getMethod());
        HttpHeaders headers = buildRequestHeaders(source, request != null ? request.getHeaders() : null);
        Object requestBody = request != null ? request.getBody() : null;
        HttpEntity<Object> entity = new HttpEntity<>(requestBody, headers);

        UiApiTestLog log = new UiApiTestLog();
        log.setEndpointId(endpointId);
        log.setRequestUrl(requestUrl);
        log.setRequestHeaders(writeJson(headers.toSingleValueMap()));
        log.setRequestQuery(writeJson(request != null ? request.getQueryParams() : null));
        log.setRequestBody(writeJson(requestBody));
        log.setCreatedBy(request != null ? request.getCreatedBy() : null);

        try {
            ResponseEntity<String> response = restTemplate.exchange(requestUrl, httpMethod, entity, String.class);
            Map<String, Object> responseHeaders = new LinkedHashMap<>(response.getHeaders().toSingleValueMap());
            Object responseBodyParsed = parsePossiblyJson(response.getBody());

            log.setResponseStatus(response.getStatusCode().value());
            log.setResponseHeaders(writeJson(responseHeaders));
            log.setResponseBody(writeJson(responseBodyParsed));
            log.setSuccessFlag(1);
            uiApiTestLogMapper.insert(log);

            return new UiApiTestResponse(
                    requestUrl,
                    response.getStatusCode().value(),
                    responseHeaders,
                    responseBodyParsed,
                    true,
                    null
            );
        } catch (RestClientException ex) {
            log.setSuccessFlag(0);
            log.setErrorMessage(ex.getMessage());
            uiApiTestLogMapper.insert(log);
            return new UiApiTestResponse(requestUrl, null, Map.of(), null, false, ex.getMessage());
        }
    }

    /**
     * 查询项目列表。
     *
     * @return 项目列表
     */
    public List<UiProject> listProjects() {
        return uiProjectMapper.selectList(new LambdaQueryWrapper<UiProject>()
                .orderByDesc(UiProject::getUpdatedAt)
                .orderByDesc(UiProject::getCreatedAt));
    }

    /**
     * 分页查询项目列表。
     *
     * @param query 分页参数
     * @return 分页后的项目列表
     */
    public PageResult<UiProject> listProjects(PageQuery query) {
        Page<UiProject> pageParam = buildPage(query);
        Page<UiProject> result = uiProjectMapper.selectPage(pageParam, new LambdaQueryWrapper<UiProject>()
                .orderByDesc(UiProject::getUpdatedAt)
                .orderByDesc(UiProject::getCreatedAt));
        return PageResult.of(result.getRecords(), result.getTotal(), query.getPage(), query.getSize());
    }

    /**
     * 创建项目。
     *
     * @param request 项目创建请求
     * @return 持久化后的项目
     */
    @Transactional
    public UiProject createProject(UiProjectRequest request) {
        validateProjectRequest(request, false);
        ensureProjectCodeUnique(request.getCode(), null);
        UiProject project = new UiProject();
        applyProjectRequest(project, request);
        uiProjectMapper.insert(project);
        return project;
    }

    /**
     * 更新项目。
     *
     * @param projectId 项目 ID
     * @param request 项目更新请求
     * @return 更新后的项目
     */
    @Transactional
    public UiProject updateProject(String projectId, UiProjectRequest request) {
        validateProjectRequest(request, true);
        UiProject project = requireProject(projectId);
        ensureProjectCodeUnique(request.getCode(), projectId);
        applyProjectRequest(project, request);
        uiProjectMapper.updateById(project);
        return project;
    }

    /**
     * 删除项目以及项目下的所有页面、节点、绑定和版本。
     *
     * @param projectId 项目 ID
     */
    @Transactional
    public void deleteProject(String projectId) {
        requireProject(projectId);
        List<UiPage> pages = listPages(projectId);
        for (UiPage page : pages) {
            deletePage(page.getId());
        }
        uiProjectMapper.deleteById(projectId);
    }

    /**
     * 查询项目下的页面列表。
     *
     * @param projectId 项目 ID
     * @return 页面列表
     */
    public List<UiPage> listPages(String projectId) {
        requireProject(projectId);
        return uiPageMapper.selectList(new LambdaQueryWrapper<UiPage>()
                .eq(UiPage::getProjectId, projectId)
                .orderByDesc(UiPage::getUpdatedAt)
                .orderByDesc(UiPage::getCreatedAt));
    }

    /**
     * 分页查询项目下的页面列表。
     *
     * @param projectId 项目 ID
     * @param query 分页参数
     * @return 分页页面列表
     */
    public PageResult<UiPage> listPages(String projectId, PageQuery query) {
        requireProject(projectId);
        Page<UiPage> pageParam = buildPage(query);
        Page<UiPage> result = uiPageMapper.selectPage(pageParam, new LambdaQueryWrapper<UiPage>()
                .eq(UiPage::getProjectId, projectId)
                .orderByDesc(UiPage::getUpdatedAt)
                .orderByDesc(UiPage::getCreatedAt));
        return PageResult.of(result.getRecords(), result.getTotal(), query.getPage(), query.getSize());
    }

    /**
     * 创建页面。
     *
     * @param projectId 项目 ID
     * @param request 页面创建请求
     * @return 新创建的页面
     */
    @Transactional
    public UiPage createPage(String projectId, UiPageRequest request) {
        requireProject(projectId);
        validatePageRequest(request, false);
        ensurePageCodeUnique(request.getCode(), null);
        UiPage page = new UiPage();
        page.setProjectId(projectId);
        applyPageRequest(page, request);
        uiPageMapper.insert(page);
        return page;
    }

    /**
     * 查询页面详情。
     *
     * <p>该方法会同时返回页面本身、页面下的节点树和节点绑定，
     * 方便前端一次性拉取工作台所需的完整上下文。
     *
     * @param pageId 页面 ID
     * @return 页面详情对象
     */
    public UiBuilderPageDetailResponse getPageDetail(String pageId) {
        UiPage page = requirePage(pageId);
        List<UiPageNode> nodes = listNodes(pageId);
        List<String> nodeIds = nodes.stream().map(UiPageNode::getId).toList();
        List<UiNodeBinding> bindings = nodeIds.isEmpty()
                ? List.of()
                : uiNodeBindingMapper.selectList(new LambdaQueryWrapper<UiNodeBinding>()
                .in(UiNodeBinding::getNodeId, nodeIds)
                .orderByAsc(UiNodeBinding::getTargetProp));
        return new UiBuilderPageDetailResponse(page, nodes, bindings);
    }

    /**
     * 更新页面基础信息。
     *
     * @param pageId 页面 ID
     * @param request 页面更新请求
     * @return 更新后的页面
     */
    @Transactional
    public UiPage updatePage(String pageId, UiPageRequest request) {
        validatePageRequest(request, true);
        UiPage page = requirePage(pageId);
        ensurePageCodeUnique(request.getCode(), pageId);
        applyPageRequest(page, request);
        uiPageMapper.updateById(page);
        return page;
    }

    /**
     * 删除页面及其所有派生数据。
     *
     * @param pageId 页面 ID
     */
    @Transactional
    public void deletePage(String pageId) {
        UiPage page = requirePage(pageId);
        List<UiPageNode> nodes = listNodes(pageId);
        List<String> nodeIds = nodes.stream().map(UiPageNode::getId).toList();
        if (!nodeIds.isEmpty()) {
            uiNodeBindingMapper.delete(new LambdaQueryWrapper<UiNodeBinding>().in(UiNodeBinding::getNodeId, nodeIds));
            uiPageNodeMapper.delete(new LambdaQueryWrapper<UiPageNode>().in(UiPageNode::getId, nodeIds));
        }
        uiSpecVersionMapper.delete(new LambdaQueryWrapper<UiSpecVersion>().eq(UiSpecVersion::getPageId, pageId));
        uiPageMapper.deleteById(page.getId());
    }

    /**
     * 查询页面下的节点列表。
     *
     * @param pageId 页面 ID
     * @return 节点列表
     */
    public List<UiPageNode> listNodes(String pageId) {
        requirePage(pageId);
        return uiPageNodeMapper.selectList(new LambdaQueryWrapper<UiPageNode>()
                .eq(UiPageNode::getPageId, pageId)
                .orderByAsc(UiPageNode::getSortOrder)
                .orderByAsc(UiPageNode::getCreatedAt));
    }

    /**
     * 分页查询页面节点列表。
     *
     * <p>控制台对外提供分页列表接口，但内部构建节点树、删除节点后代、
     * 生成预览 spec 时仍然需要完整节点集合，因此保留了同名的全量方法。
     *
     * @param pageId 页面 ID
     * @param query 分页参数
     * @return 分页节点列表
     */
    public PageResult<UiPageNode> listNodes(String pageId, PageQuery query) {
        requirePage(pageId);
        Page<UiPageNode> pageParam = buildPage(query);
        Page<UiPageNode> result = uiPageNodeMapper.selectPage(pageParam, new LambdaQueryWrapper<UiPageNode>()
                .eq(UiPageNode::getPageId, pageId)
                .orderByAsc(UiPageNode::getSortOrder)
                .orderByAsc(UiPageNode::getCreatedAt));
        return PageResult.of(result.getRecords(), result.getTotal(), query.getPage(), query.getSize());
    }

    /**
     * 创建页面节点。
     *
     * <p>如果页面当前还没有根节点，且新节点本身是顶级节点，则会自动把该节点设为页面根节点。
     *
     * @param pageId 页面 ID
     * @param request 节点创建请求
     * @return 创建后的节点
     */
    @Transactional
    public UiPageNode createNode(String pageId, UiPageNodeRequest request) {
        requirePage(pageId);
        validateNodeRequest(request, false);
        ensureNodeKeyUnique(pageId, request.getNodeKey(), null);
        UiPageNode node = new UiPageNode();
        node.setPageId(pageId);
        applyNodeRequest(node, request);
        uiPageNodeMapper.insert(node);

        UiPage page = requirePage(pageId);
        if (!StringUtils.hasText(page.getRootNodeId()) && !StringUtils.hasText(node.getParentId())) {
            page.setRootNodeId(node.getId());
            uiPageMapper.updateById(page);
        }
        return node;
    }

    /**
     * 更新页面节点。
     *
     * @param nodeId 节点 ID
     * @param request 节点更新请求
     * @return 更新后的节点
     */
    @Transactional
    public UiPageNode updateNode(String nodeId, UiPageNodeRequest request) {
        validateNodeRequest(request, true);
        UiPageNode node = requireNode(nodeId);
        ensureNodeKeyUnique(node.getPageId(), request.getNodeKey(), nodeId);
        applyNodeRequest(node, request);
        uiPageNodeMapper.updateById(node);
        return node;
    }

    /**
     * 删除节点及其全部后代节点。
     *
     * @param nodeId 节点 ID
     */
    @Transactional
    public void deleteNode(String nodeId) {
        UiPageNode node = requireNode(nodeId);
        List<String> descendantIds = collectDescendantIds(node.getPageId(), nodeId);
        descendantIds.add(nodeId);
        uiNodeBindingMapper.delete(new LambdaQueryWrapper<UiNodeBinding>().in(UiNodeBinding::getNodeId, descendantIds));
        uiPageNodeMapper.delete(new LambdaUpdateWrapper<UiPageNode>().in(UiPageNode::getId, descendantIds));

        UiPage page = requirePage(node.getPageId());
        if (Objects.equals(page.getRootNodeId(), nodeId)) {
            page.setRootNodeId(findFirstRootNodeId(page.getId()));
            uiPageMapper.updateById(page);
        }
    }

    /**
     * 查询某个节点下的字段绑定配置。
     *
     * @param nodeId 节点 ID
     * @return 字段绑定列表
     */
    public List<UiNodeBinding> listBindings(String nodeId) {
        requireNode(nodeId);
        return uiNodeBindingMapper.selectList(new LambdaQueryWrapper<UiNodeBinding>()
                .eq(UiNodeBinding::getNodeId, nodeId)
                .orderByAsc(UiNodeBinding::getTargetProp)
                .orderByAsc(UiNodeBinding::getCreatedAt));
    }

    /**
     * 分页查询某个节点下的字段绑定配置。
     *
     * @param nodeId 节点 ID
     * @param query 分页参数
     * @return 分页绑定列表
     */
    public PageResult<UiNodeBinding> listBindings(String nodeId, PageQuery query) {
        requireNode(nodeId);
        Page<UiNodeBinding> pageParam = buildPage(query);
        Page<UiNodeBinding> result = uiNodeBindingMapper.selectPage(pageParam, new LambdaQueryWrapper<UiNodeBinding>()
                .eq(UiNodeBinding::getNodeId, nodeId)
                .orderByAsc(UiNodeBinding::getTargetProp)
                .orderByAsc(UiNodeBinding::getCreatedAt));
        return PageResult.of(result.getRecords(), result.getTotal(), query.getPage(), query.getSize());
    }

    /**
     * 创建字段绑定。
     *
     * @param nodeId 节点 ID
     * @param request 字段绑定请求
     * @return 创建后的字段绑定
     */
    @Transactional
    public UiNodeBinding createBinding(String nodeId, UiNodeBindingRequest request) {
        requireNode(nodeId);
        validateBindingRequest(request, false);
        if (StringUtils.hasText(request.getEndpointId())) {
            requireEndpoint(request.getEndpointId());
        }
        UiNodeBinding binding = new UiNodeBinding();
        binding.setNodeId(nodeId);
        applyBindingRequest(binding, request);
        uiNodeBindingMapper.insert(binding);
        return binding;
    }

    /**
     * 更新字段绑定。
     *
     * @param bindingId 绑定 ID
     * @param request 绑定更新请求
     * @return 更新后的绑定
     */
    @Transactional
    public UiNodeBinding updateBinding(String bindingId, UiNodeBindingRequest request) {
        validateBindingRequest(request, true);
        UiNodeBinding binding = requireBinding(bindingId);
        if (StringUtils.hasText(request.getEndpointId())) {
            requireEndpoint(request.getEndpointId());
        }
        applyBindingRequest(binding, request);
        uiNodeBindingMapper.updateById(binding);
        return binding;
    }

    /**
     * 删除字段绑定。
     *
     * @param bindingId 绑定 ID
     */
    @Transactional
    public void deleteBinding(String bindingId) {
        requireBinding(bindingId);
        uiNodeBindingMapper.deleteById(bindingId);
    }

    /**
     * 根据当前页面配置实时生成预览 spec。
     *
     * @param pageId 页面 ID
     * @return 当前页面的预览结果
     */
    public UiPagePreviewResponse previewPage(String pageId) {
        UiPage page = requirePage(pageId);
        Map<String, Object> spec = buildSpec(page);
        return new UiPagePreviewResponse(pageId, StringUtils.hasText(page.getRootNodeId()) ? page.getRootNodeId() : null, spec);
    }

    /**
     * 查询页面版本列表。
     *
     * @param pageId 页面 ID
     * @return 发布版本列表
     */
    public List<UiSpecVersion> listVersions(String pageId) {
        requirePage(pageId);
        return uiSpecVersionMapper.selectList(new LambdaQueryWrapper<UiSpecVersion>()
                .eq(UiSpecVersion::getPageId, pageId)
                .orderByDesc(UiSpecVersion::getVersionNo));
    }

    /**
     * 分页查询页面版本列表。
     *
     * @param pageId 页面 ID
     * @param query 分页参数
     * @return 分页版本列表
     */
    public PageResult<UiSpecVersion> listVersions(String pageId, PageQuery query) {
        requirePage(pageId);
        Page<UiSpecVersion> pageParam = buildPage(query);
        Page<UiSpecVersion> result = uiSpecVersionMapper.selectPage(pageParam, new LambdaQueryWrapper<UiSpecVersion>()
                .eq(UiSpecVersion::getPageId, pageId)
                .orderByDesc(UiSpecVersion::getVersionNo));
        return PageResult.of(result.getRecords(), result.getTotal(), query.getPage(), query.getSize());
    }

    /**
     * 生成并发布新的 spec 版本。
     *
     * @param pageId 页面 ID
     * @param publishedBy 发布人
     * @return 新创建的版本记录
     */
    @Transactional
    public UiSpecVersion publishPage(String pageId, String publishedBy) {
        UiPage page = requirePage(pageId);
        Map<String, Object> spec = buildSpec(page);
        int nextVersion = listVersions(pageId).stream()
                .map(UiSpecVersion::getVersionNo)
                .max(Integer::compareTo)
                .orElse(0) + 1;

        UiSpecVersion version = new UiSpecVersion();
        version.setProjectId(page.getProjectId());
        version.setPageId(page.getId());
        version.setVersionNo(nextVersion);
        version.setPublishStatus("published");
        version.setSpecContent(writeJson(spec));
        version.setSourceSnapshot(writeJson(getPageDetail(pageId)));
        version.setPublishedBy(publishedBy);
        version.setPublishedAt(OffsetDateTime.now());
        uiSpecVersionMapper.insert(version);

        page.setStatus("published");
        uiPageMapper.updateById(page);
        return version;
    }

    /**
     * 解析 OpenAPI 文档来源。
     *
     * <p>优先级如下：
     *
     * <ol>
     *     <li>请求体中的 document</li>
     *     <li>请求体中的 documentUrl</li>
     *     <li>接口源自身配置的 docUrl</li>
     * </ol>
     *
     * <p>这样可以同时满足“手工粘贴文档”和“直接通过 Swagger 地址导入”两类使用场景。
     *
     * @param source 当前接口源
     * @param request 导入请求
     * @return OpenAPI 文档文本
     */
    private String loadOpenApiDocument(UiApiSource source, UiOpenApiImportRequest request) {
        if (request != null && StringUtils.hasText(request.getDocument())) {
            return request.getDocument();
        }

        String documentUrl = null;
        if (request != null && StringUtils.hasText(request.getDocumentUrl())) {
            documentUrl = request.getDocumentUrl();
        } else if (StringUtils.hasText(source.getDocUrl())) {
            documentUrl = source.getDocUrl();
        }

        if (!StringUtils.hasText(documentUrl)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "OpenAPI 文档内容和文档地址不能同时为空");
        }

        try {
            String response = restTemplate.getForObject(documentUrl, String.class);
            if (!StringUtils.hasText(response)) {
                throw new BusinessException(ErrorCode.BAD_REQUEST, "通过 Swagger 地址获取到的文档内容为空");
            }
            return response;
        } catch (RestClientException ex) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "Swagger 地址导入失败: " + ex.getMessage(), ex);
        }
    }

    /**
     * 校验接口源创建/更新请求。
     *
     * @param request 请求体
     * @param allowPartial 是否允许部分字段为空
     */
    private void validateSourceRequest(UiApiSourceRequest request, boolean allowPartial) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "接口源请求不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getName())) {
            requireText(request.getName(), "接口源名称不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getCode())) {
            requireText(request.getCode(), "接口源编码不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getSourceType())) {
            requireText(request.getSourceType(), "接口源类型不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getAuthType())) {
            requireText(request.getAuthType(), "认证方式不能为空");
        }
    }

    /**
     * 创建 MyBatis-Plus 分页对象。
     *
     * @param query 前端分页参数
     * @param <T> 记录类型
     * @return MyBatis-Plus 分页对象
     */
    private <T> Page<T> buildPage(PageQuery query) {
        return new Page<>(query.getPage(), query.getSize());
    }

    /**
     * 对静态列表或导入结果做内存分页。
     *
     * <p>当列表数据不适合直接走数据库分页时，例如静态元数据或一次导入后
     * 返回的“本次结果集”，统一通过该方法切片，保持控制器层返回格式一致。
     *
     * @param items 原始列表
     * @param query 分页参数
     * @param <T> 元素类型
     * @return 分页结果
     */
    private <T> PageResult<T> paginateList(List<T> items, PageQuery query) {
        if (items == null || items.isEmpty()) {
            return PageResult.empty(query.getPage(), query.getSize());
        }
        int fromIndex = Math.min(query.getOffset(), items.size());
        int toIndex = Math.min(fromIndex + query.getSize(), items.size());
        return PageResult.of(new ArrayList<>(items.subList(fromIndex, toIndex)), items.size(), query.getPage(), query.getSize());
    }

    /**
     * 校验接口定义请求。
     *
     * @param request 请求体
     * @param allowPartial 是否允许部分字段为空
     */
    private void validateEndpointRequest(UiApiEndpointRequest request, boolean allowPartial) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "接口定义请求不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getSourceId())) {
            requireText(request.getSourceId(), "sourceId 不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getName())) {
            requireText(request.getName(), "接口名称不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getPath())) {
            requireText(request.getPath(), "接口路径不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getMethod())) {
            requireText(request.getMethod(), "HTTP 方法不能为空");
        }
    }

    /**
     * 校验项目请求。
     *
     * @param request 请求体
     * @param allowPartial 是否允许部分字段为空
     */
    private void validateProjectRequest(UiProjectRequest request, boolean allowPartial) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "项目请求不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getName())) {
            requireText(request.getName(), "项目名称不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getCode())) {
            requireText(request.getCode(), "项目编码不能为空");
        }
    }

    /**
     * 校验页面请求。
     *
     * @param request 请求体
     * @param allowPartial 是否允许部分字段为空
     */
    private void validatePageRequest(UiPageRequest request, boolean allowPartial) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "页面请求不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getName())) {
            requireText(request.getName(), "页面名称不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getCode())) {
            requireText(request.getCode(), "页面编码不能为空");
        }
    }

    /**
     * 校验页面节点请求。
     *
     * @param request 请求体
     * @param allowPartial 是否允许部分字段为空
     */
    private void validateNodeRequest(UiPageNodeRequest request, boolean allowPartial) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "节点请求不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getNodeKey())) {
            requireText(request.getNodeKey(), "nodeKey 不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getNodeType())) {
            requireText(request.getNodeType(), "nodeType 不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getNodeName())) {
            requireText(request.getNodeName(), "nodeName 不能为空");
        }
    }

    /**
     * 校验字段绑定请求。
     *
     * @param request 请求体
     * @param allowPartial 是否允许部分字段为空
     */
    private void validateBindingRequest(UiNodeBindingRequest request, boolean allowPartial) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "字段绑定请求不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getBindingType())) {
            requireText(request.getBindingType(), "bindingType 不能为空");
        }
        if (!allowPartial || StringUtils.hasText(request.getTargetProp())) {
            requireText(request.getTargetProp(), "targetProp 不能为空");
        }
    }

    /**
     * 将接口源请求体写入实体对象。
     *
     * @param source 目标实体
     * @param request 请求体
     */
    private void applySourceRequest(UiApiSource source, UiApiSourceRequest request) {
        source.setName(request.getName());
        source.setCode(request.getCode());
        source.setDescription(request.getDescription());
        source.setSourceType(request.getSourceType());
        source.setBaseUrl(request.getBaseUrl());
        source.setDocUrl(request.getDocUrl());
        source.setAuthType(request.getAuthType());
        source.setAuthConfig(defaultIfBlank(request.getAuthConfig(), "{}"));
        source.setDefaultHeaders(defaultIfBlank(request.getDefaultHeaders(), "{}"));
        source.setEnv(defaultIfBlank(request.getEnv(), "dev"));
        source.setStatus(defaultIfBlank(request.getStatus(), "draft"));
        source.setCreatedBy(request.getCreatedBy());
    }

    /**
     * 将接口定义请求体写入实体对象。
     *
     * @param endpoint 目标实体
     * @param request 请求体
     */
    private void applyEndpointRequest(UiApiEndpoint endpoint, UiApiEndpointRequest request) {
        endpoint.setSourceId(request.getSourceId());
        endpoint.setTagId(request.getTagId());
        endpoint.setName(request.getName());
        endpoint.setPath(request.getPath());
        endpoint.setMethod(request.getMethod() != null ? request.getMethod().toUpperCase(Locale.ROOT) : null);
        endpoint.setSummary(request.getSummary());
        endpoint.setRequestContentType(request.getRequestContentType());
        endpoint.setRequestSchema(defaultIfBlank(request.getRequestSchema(), "{}"));
        endpoint.setResponseSchema(defaultIfBlank(request.getResponseSchema(), "{}"));
        endpoint.setSampleRequest(defaultIfBlank(request.getSampleRequest(), "{}"));
        endpoint.setSampleResponse(defaultIfBlank(request.getSampleResponse(), "{}"));
        endpoint.setStatus(defaultIfBlank(request.getStatus(), "active"));
    }

    /**
     * 将项目请求体写入实体对象。
     *
     * @param project 目标实体
     * @param request 请求体
     */
    private void applyProjectRequest(UiProject project, UiProjectRequest request) {
        project.setName(request.getName());
        project.setCode(request.getCode());
        project.setDescription(request.getDescription());
        project.setCategory(request.getCategory());
        project.setStatus(defaultIfBlank(request.getStatus(), "draft"));
        project.setCreatedBy(request.getCreatedBy());
    }

    /**
     * 将页面请求体写入实体对象。
     *
     * @param page 目标实体
     * @param request 请求体
     */
    private void applyPageRequest(UiPage page, UiPageRequest request) {
        page.setName(request.getName());
        page.setCode(request.getCode());
        page.setTitle(request.getTitle());
        page.setRoutePath(request.getRoutePath());
        if (StringUtils.hasText(request.getRootNodeId())) {
            page.setRootNodeId(request.getRootNodeId());
        }
        page.setLayoutType(defaultIfBlank(request.getLayoutType(), "page"));
        page.setStatus(defaultIfBlank(request.getStatus(), "draft"));
    }

    /**
     * 将节点请求体写入实体对象。
     *
     * @param node 目标实体
     * @param request 请求体
     */
    private void applyNodeRequest(UiPageNode node, UiPageNodeRequest request) {
        node.setParentId(request.getParentId());
        node.setNodeKey(request.getNodeKey());
        node.setNodeType(request.getNodeType());
        node.setNodeName(request.getNodeName());
        node.setSortOrder(request.getSortOrder() != null ? request.getSortOrder() : 0);
        node.setSlotName(defaultIfBlank(request.getSlotName(), "default"));
        node.setPropsConfig(defaultIfBlank(request.getPropsConfig(), "{}"));
        node.setStyleConfig(defaultIfBlank(request.getStyleConfig(), "{}"));
        node.setStatus(defaultIfBlank(request.getStatus(), "active"));
    }

    /**
     * 将字段绑定请求体写入实体对象。
     *
     * @param binding 目标实体
     * @param request 请求体
     */
    private void applyBindingRequest(UiNodeBinding binding, UiNodeBindingRequest request) {
        binding.setEndpointId(request.getEndpointId());
        binding.setBindingType(defaultIfBlank(request.getBindingType(), "static"));
        binding.setTargetProp(request.getTargetProp());
        binding.setSourcePath(request.getSourcePath());
        binding.setTransformScript(request.getTransformScript());
        binding.setDefaultValue(request.getDefaultValue());
        binding.setRequiredFlag(Boolean.TRUE.equals(request.getRequiredFlag()));
    }

    /**
     * 根据页面配置组装 json-render spec。
     *
     * <p>生成规则：
     *
     * <ol>
     *     <li>查询页面下全部节点并按 parentId / sortOrder 组织层级</li>
     *     <li>读取每个节点的静态 props</li>
     *     <li>应用字段绑定，把接口样例响应映射到目标属性</li>
     *     <li>按 json-render 规范输出 root + elements 扁平结构</li>
     * </ol>
     *
     * @param page 页面实体
     * @return 标准 json-render spec
     */
    private Map<String, Object> buildSpec(UiPage page) {
        List<UiPageNode> nodes = listNodes(page.getId());
        if (nodes.isEmpty()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "页面下还没有节点，无法生成 spec");
        }

        Map<String, UiPageNode> nodeById = new LinkedHashMap<>();
        for (UiPageNode node : nodes) {
            nodeById.put(node.getId(), node);
        }
        String rootNodeId = StringUtils.hasText(page.getRootNodeId()) ? page.getRootNodeId() : findFirstRootNodeId(page.getId());
        if (!StringUtils.hasText(rootNodeId) || !nodeById.containsKey(rootNodeId)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "页面根节点不存在，无法生成 spec");
        }

        Map<String, List<UiPageNode>> childrenByParentId = new LinkedHashMap<>();
        for (UiPageNode node : nodes) {
            childrenByParentId.computeIfAbsent(node.getParentId(), key -> new ArrayList<>()).add(node);
        }
        childrenByParentId.values().forEach(childNodes -> childNodes.sort(Comparator.comparing(UiPageNode::getSortOrder).thenComparing(UiPageNode::getCreatedAt)));

        List<String> nodeIds = nodes.stream().map(UiPageNode::getId).toList();
        List<UiNodeBinding> bindings = nodeIds.isEmpty()
                ? List.of()
                : uiNodeBindingMapper.selectList(new LambdaQueryWrapper<UiNodeBinding>().in(UiNodeBinding::getNodeId, nodeIds));
        Map<String, List<UiNodeBinding>> bindingsByNodeId = new LinkedHashMap<>();
        for (UiNodeBinding binding : bindings) {
            bindingsByNodeId.computeIfAbsent(binding.getNodeId(), key -> new ArrayList<>()).add(binding);
        }

        Map<String, Object> elements = new LinkedHashMap<>();
        for (UiPageNode node : nodes) {
            Map<String, Object> props = readMap(node.getPropsConfig());
            applyBindings(props, bindingsByNodeId.getOrDefault(node.getId(), List.of()));

            List<String> childKeys = childrenByParentId.getOrDefault(node.getId(), List.of()).stream()
                    .map(UiPageNode::getNodeKey)
                    .toList();

            Map<String, Object> element = new LinkedHashMap<>();
            element.put("type", node.getNodeType());
            element.put("props", props);
            element.put("children", new ArrayList<>(childKeys));
            elements.put(node.getNodeKey(), element);
        }

        Map<String, Object> spec = new LinkedHashMap<>();
        spec.put("root", nodeById.get(rootNodeId).getNodeKey());
        spec.put("elements", elements);
        return spec;
    }

    /**
     * 将字段绑定结果应用到节点 props。
     *
     * <p>绑定的值默认来自接口样例响应，若未提取到有效值，则回退到 defaultValue。
     *
     * @param props 节点当前 props
     * @param bindings 节点字段绑定列表
     */
    private void applyBindings(Map<String, Object> props, List<UiNodeBinding> bindings) {
        for (UiNodeBinding binding : bindings) {
            Object value = null;
            if (StringUtils.hasText(binding.getEndpointId()) && StringUtils.hasText(binding.getSourcePath())) {
                UiApiEndpoint endpoint = requireEndpoint(binding.getEndpointId());
                JsonNode sample = readJsonTree(defaultIfBlank(endpoint.getSampleResponse(), "{}"), "接口样例响应解析失败");
                JsonNode extracted = extractJsonPath(sample, binding.getSourcePath());
                if (extracted != null && !extracted.isMissingNode() && !extracted.isNull()) {
                    value = objectMapper.convertValue(extracted, Object.class);
                }
            }
            if (value == null && StringUtils.hasText(binding.getDefaultValue())) {
                value = parsePossiblyJson(binding.getDefaultValue());
            }
            value = transformValue(value, binding, props);
            setNestedProperty(props, binding.getTargetProp(), value);
        }
    }

    /**
     * 对绑定结果执行内置转换器。
     *
     * @param value 原始绑定值
     * @param binding 绑定定义
     * @param props 当前 props
     * @return 转换后的值
     */
    private Object transformValue(Object value, UiNodeBinding binding, Map<String, Object> props) {
        if (!StringUtils.hasText(binding.getTransformScript()) || value == null) {
            return value;
        }
        return switch (binding.getTransformScript()) {
            case "tableRows" -> transformTableRows(value, props);
            default -> value;
        };
    }

    /**
     * 将对象数组转换成 Table 组件需要的二维数组。
     *
     * <p>当前会读取 props.columns 中的列顺序，并按列名从对象数组中逐行提取值。
     *
     * @param value 原始对象数组
     * @param props 节点 props
     * @return Table 组件可直接消费的二维数组
     */
    private Object transformTableRows(Object value, Map<String, Object> props) {
        if (!(value instanceof List<?> items)) {
            return value;
        }
        Object columnsObj = props.get("columns");
        if (!(columnsObj instanceof List<?> columns)) {
            return value;
        }
        List<List<Object>> rows = new ArrayList<>();
        for (Object item : items) {
            if (!(item instanceof Map<?, ?> mapItem)) {
                continue;
            }
            List<Object> row = new ArrayList<>();
            for (Object column : columns) {
                row.add(mapItem.get(String.valueOf(column)));
            }
            rows.add(row);
        }
        return rows;
    }

    /**
     * 从接口样例响应中提取 JSONPath 对应的节点。
     *
     * <p>当前实现支持简单路径、数组下标和 `[*]` 列表节点。
     *
     * @param root 根 JSON 节点
     * @param jsonPath JSONPath 表达式
     * @return 提取到的 JSON 节点
     */
    private JsonNode extractJsonPath(JsonNode root, String jsonPath) {
        if (!StringUtils.hasText(jsonPath) || "$".equals(jsonPath.trim())) {
            return root;
        }
        String normalized = jsonPath.trim();
        if (normalized.startsWith("$.")) {
            normalized = normalized.substring(2);
        } else if (normalized.startsWith("$")) {
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
            if (token.endsWith("[*]")) {
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

    /**
     * 把绑定值写入嵌套属性路径。
     *
     * <p>例如 `option.series` 会被展开成多层 Map 结构。
     *
     * @param root 根 props
     * @param path 目标属性路径
     * @param value 待写入的值
     */
    private void setNestedProperty(Map<String, Object> root, String path, Object value) {
        if (!StringUtils.hasText(path)) {
            return;
        }
        String[] segments = path.split("\\.");
        Map<String, Object> current = root;
        for (int i = 0; i < segments.length - 1; i++) {
            Object child = current.get(segments[i]);
            if (!(child instanceof Map<?, ?>)) {
                child = new LinkedHashMap<String, Object>();
                current.put(segments[i], child);
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> next = (Map<String, Object>) child;
            current = next;
        }
        current.put(segments[segments.length - 1], value);
    }

    /**
     * 组装接口联调请求地址。
     *
     * @param source 接口源
     * @param endpoint 接口定义
     * @param queryParams 调用时的查询参数
     * @return 最终请求地址
     */
    private String buildRequestUrl(UiApiSource source, UiApiEndpoint endpoint, Map<String, Object> queryParams) {
        String baseUrl = defaultIfBlank(source.getBaseUrl(), "");
        String path = defaultIfBlank(endpoint.getPath(), "");
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(baseUrl + path);
        Map<String, Object> safeQueryParams = queryParams != null ? queryParams : Collections.emptyMap();
        safeQueryParams.forEach((key, value) -> {
            if (value instanceof Iterable<?> iterable) {
                for (Object item : iterable) {
                    builder.queryParam(key, item);
                }
            } else if (value != null) {
                builder.queryParam(key, value);
            }
        });

        Map<String, Object> authConfig = readMap(source.getAuthConfig());
        if ("api_key".equals(source.getAuthType()) && authConfig.containsKey("queryName") && authConfig.containsKey("queryValue")) {
            builder.queryParam(String.valueOf(authConfig.get("queryName")), authConfig.get("queryValue"));
        }
        return builder.build(true).toUriString();
    }

    /**
     * 组装接口联调请求头。
     *
     * <p>请求头来源按以下顺序叠加：
     *
     * <ol>
     *     <li>默认 Content-Type</li>
     *     <li>接口源默认请求头</li>
     *     <li>本次联调显式传入的请求头</li>
     *     <li>接口源认证配置推导出的认证头</li>
     * </ol>
     *
     * @param source 接口源
     * @param requestHeaders 本次联调额外传入的请求头
     * @return 最终请求头
     */
    private HttpHeaders buildRequestHeaders(UiApiSource source, Map<String, Object> requestHeaders) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        readMap(source.getDefaultHeaders()).forEach((key, value) -> headers.set(key, String.valueOf(value)));
        if (requestHeaders != null) {
            requestHeaders.forEach((key, value) -> headers.set(key, String.valueOf(value)));
        }

        Map<String, Object> authConfig = readMap(source.getAuthConfig());
        switch (defaultIfBlank(source.getAuthType(), "none")) {
            case "api_key" -> {
                if (authConfig.containsKey("headerName") && authConfig.containsKey("headerValue")) {
                    headers.set(String.valueOf(authConfig.get("headerName")), String.valueOf(authConfig.get("headerValue")));
                }
            }
            case "bearer_token" -> {
                if (authConfig.containsKey("token")) {
                    headers.setBearerAuth(String.valueOf(authConfig.get("token")));
                } else if (authConfig.containsKey("accessToken")) {
                    headers.setBearerAuth(String.valueOf(authConfig.get("accessToken")));
                }
            }
            case "basic_auth" -> {
                String username = String.valueOf(authConfig.getOrDefault("username", ""));
                String password = String.valueOf(authConfig.getOrDefault("password", ""));
                String encoded = Base64.getEncoder().encodeToString((username + ":" + password).getBytes(StandardCharsets.UTF_8));
                headers.set(HttpHeaders.AUTHORIZATION, "Basic " + encoded);
            }
            case "oauth2_client" -> {
                if (authConfig.containsKey("accessToken")) {
                    headers.setBearerAuth(String.valueOf(authConfig.get("accessToken")));
                }
            }
            default -> {
            }
        }
        return headers;
    }

    /**
     * 根据 OpenAPI operation 的 tags 字段解析标签。
     *
     * <p>当前取 tags 数组中的第一个标签作为接口主标签，并在本地标签表中自动创建或复用。
     *
     * @param sourceId 接口源 ID
     * @param operationNode OpenAPI operation 节点
     * @return 解析到的标签 ID，没有标签时返回 null
     */
    private String resolveTagId(String sourceId, JsonNode operationNode) {
        JsonNode tagsNode = operationNode.path("tags");
        if (!tagsNode.isArray() || tagsNode.isEmpty()) {
            return null;
        }
        String tagName = tagsNode.get(0).asText(null);
        if (!StringUtils.hasText(tagName)) {
            return null;
        }
        return findOrCreateTag(sourceId, tagName).getId();
    }

    /**
     * 查找或创建接口标签。
     *
     * @param sourceId 接口源 ID
     * @param tagName 标签名称
     * @return 标签实体
     */
    private UiApiTag findOrCreateTag(String sourceId, String tagName) {
        String tagCode = toTagCode(tagName);
        UiApiTag existingTag = uiApiTagMapper.selectOne(new LambdaQueryWrapper<UiApiTag>()
                .eq(UiApiTag::getSourceId, sourceId)
                .eq(UiApiTag::getCode, tagCode)
                .last("limit 1"));
        if (existingTag != null) {
            return existingTag;
        }

        UiApiTag tag = new UiApiTag();
        tag.setSourceId(sourceId);
        tag.setName(tagName);
        tag.setCode(tagCode);
        tag.setDescription("由 OpenAPI tags 自动导入");
        uiApiTagMapper.insert(tag);
        return tag;
    }

    /**
     * 为接口定义补充 tagName。
     *
     * @param endpoints 接口定义列表
     * @param sourceId 接口源 ID
     */
    private void attachTagNames(List<UiApiEndpoint> endpoints, String sourceId) {
        if (endpoints == null || endpoints.isEmpty()) {
            return;
        }
        Map<String, UiApiTag> tagById = loadTagMapBySourceId(sourceId);
        for (UiApiEndpoint endpoint : endpoints) {
            if (StringUtils.hasText(endpoint.getTagId())) {
                UiApiTag tag = tagById.get(endpoint.getTagId());
                endpoint.setTagName(tag != null ? tag.getName() : null);
            }
        }
    }

    private Map<String, UiApiTag> loadTagMapBySourceId(String sourceId) {
        List<UiApiTag> tags = uiApiTagMapper.selectList(new LambdaQueryWrapper<UiApiTag>()
                .eq(UiApiTag::getSourceId, sourceId));
        Map<String, UiApiTag> tagById = new LinkedHashMap<>();
        for (UiApiTag tag : tags) {
            tagById.put(tag.getId(), tag);
        }
        return tagById;
    }

    private String toTagCode(String tagName) {
        String normalized = tagName.trim().toLowerCase(Locale.ROOT);
        return StringUtils.hasText(normalized) ? normalized : "default_tag";
    }

    private UiApiSource requireSource(String sourceId) {
        UiApiSource source = uiApiSourceMapper.selectById(sourceId);
        if (source == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "接口源不存在: " + sourceId);
        }
        return source;
    }

    private UiApiEndpoint requireEndpoint(String endpointId) {
        UiApiEndpoint endpoint = uiApiEndpointMapper.selectById(endpointId);
        if (endpoint == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "接口定义不存在: " + endpointId);
        }
        return endpoint;
    }

    private UiApiTag requireTag(String tagId) {
        UiApiTag tag = uiApiTagMapper.selectById(tagId);
        if (tag == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "接口标签不存在: " + tagId);
        }
        return tag;
    }

    private UiApiTag requireTagInSource(String tagId, String sourceId) {
        UiApiTag tag = requireTag(tagId);
        if (!Objects.equals(tag.getSourceId(), sourceId)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "接口标签不属于当前接口源: " + tagId);
        }
        return tag;
    }

    private UiProject requireProject(String projectId) {
        UiProject project = uiProjectMapper.selectById(projectId);
        if (project == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "项目不存在: " + projectId);
        }
        return project;
    }

    private UiPage requirePage(String pageId) {
        UiPage page = uiPageMapper.selectById(pageId);
        if (page == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "页面不存在: " + pageId);
        }
        return page;
    }

    private UiPageNode requireNode(String nodeId) {
        UiPageNode node = uiPageNodeMapper.selectById(nodeId);
        if (node == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "节点不存在: " + nodeId);
        }
        return node;
    }

    private UiNodeBinding requireBinding(String bindingId) {
        UiNodeBinding binding = uiNodeBindingMapper.selectById(bindingId);
        if (binding == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "字段绑定不存在: " + bindingId);
        }
        return binding;
    }

    private void ensureSourceCodeUnique(String code, String excludeId) {
        QueryWrapper<UiApiSource> wrapper = new QueryWrapper<>();
        wrapper.eq("code", code);
        if (StringUtils.hasText(excludeId)) {
            wrapper.ne("id", excludeId);
        }
        if (uiApiSourceMapper.selectCount(wrapper) > 0) {
            throw new BusinessException(ErrorCode.DUPLICATE_ENTRY, "接口源编码已存在: " + code);
        }
    }

    private void ensureProjectCodeUnique(String code, String excludeId) {
        QueryWrapper<UiProject> wrapper = new QueryWrapper<>();
        wrapper.eq("code", code);
        if (StringUtils.hasText(excludeId)) {
            wrapper.ne("id", excludeId);
        }
        if (uiProjectMapper.selectCount(wrapper) > 0) {
            throw new BusinessException(ErrorCode.DUPLICATE_ENTRY, "项目编码已存在: " + code);
        }
    }

    private void ensurePageCodeUnique(String code, String excludeId) {
        QueryWrapper<UiPage> wrapper = new QueryWrapper<>();
        wrapper.eq("code", code);
        if (StringUtils.hasText(excludeId)) {
            wrapper.ne("id", excludeId);
        }
        if (uiPageMapper.selectCount(wrapper) > 0) {
            throw new BusinessException(ErrorCode.DUPLICATE_ENTRY, "页面编码已存在: " + code);
        }
    }

    private void ensureNodeKeyUnique(String pageId, String nodeKey, String excludeId) {
        QueryWrapper<UiPageNode> wrapper = new QueryWrapper<>();
        wrapper.eq("page_id", pageId).eq("node_key", nodeKey);
        if (StringUtils.hasText(excludeId)) {
            wrapper.ne("id", excludeId);
        }
        if (uiPageNodeMapper.selectCount(wrapper) > 0) {
            throw new BusinessException(ErrorCode.DUPLICATE_ENTRY, "页面节点 key 已存在: " + nodeKey);
        }
    }

    private UiApiEndpoint findEndpointBySourceAndMethodPath(String sourceId, String method, String path) {
        return uiApiEndpointMapper.selectOne(new LambdaQueryWrapper<UiApiEndpoint>()
                .eq(UiApiEndpoint::getSourceId, sourceId)
                .eq(UiApiEndpoint::getMethod, method)
                .eq(UiApiEndpoint::getPath, path)
                .last("limit 1"));
    }

    private List<String> collectDescendantIds(String pageId, String nodeId) {
        List<UiPageNode> nodes = listNodes(pageId);
        Map<String, List<String>> childIdsByParent = new LinkedHashMap<>();
        for (UiPageNode node : nodes) {
            if (StringUtils.hasText(node.getParentId())) {
                childIdsByParent.computeIfAbsent(node.getParentId(), key -> new ArrayList<>()).add(node.getId());
            }
        }
        List<String> result = new ArrayList<>();
        collectDescendantIds(nodeId, childIdsByParent, result);
        return result;
    }

    private void collectDescendantIds(String parentId, Map<String, List<String>> childIdsByParent, List<String> result) {
        for (String childId : childIdsByParent.getOrDefault(parentId, List.of())) {
            result.add(childId);
            collectDescendantIds(childId, childIdsByParent, result);
        }
    }

    private String findFirstRootNodeId(String pageId) {
        return listNodes(pageId).stream()
                .filter(node -> !StringUtils.hasText(node.getParentId()))
                .min(Comparator.comparing(UiPageNode::getSortOrder).thenComparing(UiPageNode::getCreatedAt))
                .map(UiPageNode::getId)
                .orElse(null);
    }

    /**
     * 提取并展开请求 schema。
     *
     * <p>如果 schema 内包含本地 `$ref`，例如 `#/components/schemas/ErpCallbackNotifyDTO`，
     * 这里会递归解析到 components 中对应的真实定义，并把结果展开成最终对象。
     *
     * @param rootDocument OpenAPI 文档根节点
     * @param operationNode 当前接口 operation 节点
     * @return 展开后的请求 schema
     */
    private JsonNode extractRequestSchema(JsonNode rootDocument, JsonNode operationNode) {
        JsonNode requestBody = operationNode.path("requestBody").path("content");
        if (!requestBody.isObject()) {
            return null;
        }
        Iterator<String> fieldNames = requestBody.fieldNames();
        if (!fieldNames.hasNext()) {
            return null;
        }
        String contentType = fieldNames.next();
        return resolveSchemaNode(rootDocument, requestBody.path(contentType).path("schema"), new HashSet<>());
    }

    private String extractRequestContentType(JsonNode operationNode) {
        JsonNode requestBody = operationNode.path("requestBody").path("content");
        if (!requestBody.isObject()) {
            return null;
        }
        Iterator<String> fieldNames = requestBody.fieldNames();
        return fieldNames.hasNext() ? fieldNames.next() : null;
    }

    /**
     * 提取并展开响应 schema。
     *
     * @param rootDocument OpenAPI 文档根节点
     * @param operationNode 当前接口 operation 节点
     * @return 展开后的响应 schema
     */
    private JsonNode extractResponseSchema(JsonNode rootDocument, JsonNode operationNode) {
        JsonNode responseNode = extractPrimaryResponse(operationNode);
        if (responseNode == null) {
            return null;
        }
        JsonNode contentNode = responseNode.path("content");
        if (!contentNode.isObject()) {
            return null;
        }
        Iterator<String> fieldNames = contentNode.fieldNames();
        if (!fieldNames.hasNext()) {
            return null;
        }
        String contentType = fieldNames.next();
        return resolveSchemaNode(rootDocument, contentNode.path(contentType).path("schema"), new HashSet<>());
    }

    /**
     * 提取请求样例。
     *
     * <p>优先使用文档中显式给出的 `example/examples`；如果没有，再基于展开后的 schema
     * 自动生成一个可读样例，这样前端配置时至少能看到字段骨架而不是裸 `$ref`。
     *
     * @param rootDocument OpenAPI 文档根节点
     * @param operationNode 当前接口 operation 节点
     * @return 请求样例
     */
    private JsonNode extractRequestExample(JsonNode rootDocument, JsonNode operationNode) {
        JsonNode requestBody = operationNode.path("requestBody").path("content");
        if (!requestBody.isObject()) {
            return null;
        }
        Iterator<String> fieldNames = requestBody.fieldNames();
        if (!fieldNames.hasNext()) {
            return null;
        }
        String contentType = fieldNames.next();
        JsonNode mediaNode = requestBody.path(contentType);
        JsonNode example = mediaNode.path("example");
        if (!example.isMissingNode() && !example.isNull()) {
            return example;
        }
        JsonNode examplesNode = mediaNode.path("examples");
        if (examplesNode.isObject() && examplesNode.fields().hasNext()) {
            return examplesNode.fields().next().getValue().path("value");
        }
        JsonNode resolvedSchema = resolveSchemaNode(rootDocument, mediaNode.path("schema"), new HashSet<>());
        return buildExampleFromSchema(resolvedSchema);
    }

    /**
     * 提取响应样例。
     *
     * @param rootDocument OpenAPI 文档根节点
     * @param operationNode 当前接口 operation 节点
     * @return 响应样例
     */
    private JsonNode extractResponseExample(JsonNode rootDocument, JsonNode operationNode) {
        JsonNode responseNode = extractPrimaryResponse(operationNode);
        if (responseNode == null) {
            return null;
        }
        JsonNode contentNode = responseNode.path("content");
        if (!contentNode.isObject()) {
            return null;
        }
        Iterator<String> fieldNames = contentNode.fieldNames();
        if (!fieldNames.hasNext()) {
            return null;
        }
        String contentType = fieldNames.next();
        JsonNode mediaNode = contentNode.path(contentType);
        JsonNode example = mediaNode.path("example");
        if (!example.isMissingNode() && !example.isNull()) {
            return example;
        }
        JsonNode examplesNode = mediaNode.path("examples");
        if (examplesNode.isObject() && examplesNode.fields().hasNext()) {
            return examplesNode.fields().next().getValue().path("value");
        }
        JsonNode resolvedSchema = resolveSchemaNode(rootDocument, mediaNode.path("schema"), new HashSet<>());
        return buildExampleFromSchema(resolvedSchema);
    }

    /**
     * 递归展开 OpenAPI schema 中的本地 `$ref`。
     *
     * <p>当前仅支持 OpenAPI 文档内的本地引用，例如 `#/components/schemas/UserDTO`。
     * 解析时会处理 `properties`、`items`、`allOf`、`oneOf`、`anyOf` 等常见节点，
     * 以便最终落库的是一个更接近实际结构的可读 schema。
     *
     * @param rootDocument OpenAPI 根文档
     * @param schemaNode 当前 schema 节点
     * @param visitedRefs 已访问引用，防止循环引用导致无限递归
     * @return 展开后的 schema
     */
    private JsonNode resolveSchemaNode(JsonNode rootDocument, JsonNode schemaNode, Set<String> visitedRefs) {
        if (schemaNode == null || schemaNode.isMissingNode() || schemaNode.isNull()) {
            return null;
        }

        if (schemaNode.isObject() && schemaNode.has("$ref")) {
            String ref = schemaNode.path("$ref").asText();
            if (!StringUtils.hasText(ref)) {
                return schemaNode;
            }
            if (!visitedRefs.add(ref)) {
                return schemaNode;
            }

            JsonNode referencedNode = resolveLocalRef(rootDocument, ref);
            JsonNode resolvedReferencedNode = resolveSchemaNode(rootDocument, referencedNode, visitedRefs);
            if (resolvedReferencedNode == null) {
                return schemaNode;
            }

            ObjectNode mergedNode = resolvedReferencedNode.deepCopy();
            Iterator<Map.Entry<String, JsonNode>> fields = schemaNode.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();
                if ("$ref".equals(field.getKey())) {
                    continue;
                }
                mergedNode.set(field.getKey(), resolveSchemaNode(rootDocument, field.getValue(), new HashSet<>(visitedRefs)));
            }
            return mergedNode;
        }

        if (schemaNode.isObject()) {
            ObjectNode resolvedNode = schemaNode.deepCopy();
            resolveObjectField(rootDocument, resolvedNode, "items", visitedRefs);
            resolveObjectField(rootDocument, resolvedNode, "additionalProperties", visitedRefs);
            resolveObjectField(rootDocument, resolvedNode, "not", visitedRefs);

            JsonNode propertiesNode = resolvedNode.path("properties");
            if (propertiesNode.isObject()) {
                ObjectNode resolvedProperties = objectMapper.createObjectNode();
                Iterator<Map.Entry<String, JsonNode>> fields = propertiesNode.fields();
                while (fields.hasNext()) {
                    Map.Entry<String, JsonNode> field = fields.next();
                    resolvedProperties.set(field.getKey(), resolveSchemaNode(rootDocument, field.getValue(), new HashSet<>(visitedRefs)));
                }
                resolvedNode.set("properties", resolvedProperties);
            }

            resolveArrayField(rootDocument, resolvedNode, "oneOf", visitedRefs);
            resolveArrayField(rootDocument, resolvedNode, "anyOf", visitedRefs);

            JsonNode allOfNode = resolvedNode.path("allOf");
            if (allOfNode.isArray()) {
                ObjectNode mergedAllOfNode = mergeAllOfSchemas(rootDocument, allOfNode, visitedRefs);
                Iterator<Map.Entry<String, JsonNode>> fields = mergedAllOfNode.fields();
                while (fields.hasNext()) {
                    Map.Entry<String, JsonNode> field = fields.next();
                    resolvedNode.set(field.getKey(), field.getValue());
                }
                resolvedNode.remove("allOf");
            }

            return resolvedNode;
        }

        if (schemaNode.isArray()) {
            ArrayNode resolvedArray = objectMapper.createArrayNode();
            for (JsonNode item : schemaNode) {
                resolvedArray.add(resolveSchemaNode(rootDocument, item, new HashSet<>(visitedRefs)));
            }
            return resolvedArray;
        }

        return schemaNode;
    }

    /**
     * 根据 schema 自动构造一个兜底样例。
     *
     * <p>这个逻辑主要用于 OpenAPI 文档没有显式 `example` 时的降级处理，
     * 让 `sample_request/sample_response` 至少能保留字段结构，便于 UI Builder 做字段绑定。
     *
     * @param schemaNode 展开后的 schema
     * @return 自动生成的样例
     */
    private JsonNode buildExampleFromSchema(JsonNode schemaNode) {
        if (schemaNode == null || schemaNode.isMissingNode() || schemaNode.isNull()) {
            return null;
        }
        if (schemaNode.has("example") && !schemaNode.path("example").isNull()) {
            return schemaNode.path("example").deepCopy();
        }
        if (schemaNode.has("default") && !schemaNode.path("default").isNull()) {
            return schemaNode.path("default").deepCopy();
        }
        if (schemaNode.has("enum") && schemaNode.path("enum").isArray() && !schemaNode.path("enum").isEmpty()) {
            return schemaNode.path("enum").get(0).deepCopy();
        }

        String type = schemaNode.path("type").asText(null);
        if ("object".equals(type) || schemaNode.path("properties").isObject()) {
            ObjectNode objectNode = objectMapper.createObjectNode();
            JsonNode properties = schemaNode.path("properties");
            Iterator<Map.Entry<String, JsonNode>> fields = properties.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();
                JsonNode childExample = buildExampleFromSchema(field.getValue());
                objectNode.set(field.getKey(), childExample != null ? childExample : objectMapper.nullNode());
            }
            return objectNode;
        }
        if ("array".equals(type) || schemaNode.path("items").isObject()) {
            ArrayNode arrayNode = objectMapper.createArrayNode();
            JsonNode childExample = buildExampleFromSchema(schemaNode.path("items"));
            if (childExample != null) {
                arrayNode.add(childExample);
            }
            return arrayNode;
        }
        if ("integer".equals(type)) {
            return objectMapper.getNodeFactory().numberNode(0);
        }
        if ("number".equals(type)) {
            return objectMapper.getNodeFactory().numberNode(0);
        }
        if ("boolean".equals(type)) {
            return objectMapper.getNodeFactory().booleanNode(false);
        }
        if ("string".equals(type)) {
            String format = schemaNode.path("format").asText("");
            if ("date-time".equals(format)) {
                return objectMapper.getNodeFactory().textNode("2026-01-01T00:00:00Z");
            }
            if ("date".equals(format)) {
                return objectMapper.getNodeFactory().textNode("2026-01-01");
            }
            return objectMapper.getNodeFactory().textNode("");
        }
        return objectMapper.nullNode();
    }

    /**
     * 解析本地 `$ref` 路径。
     *
     * @param rootDocument OpenAPI 根文档
     * @param ref 引用路径
     * @return 引用指向的节点
     */
    private JsonNode resolveLocalRef(JsonNode rootDocument, String ref) {
        if (!StringUtils.hasText(ref) || !ref.startsWith("#/")) {
            return null;
        }

        JsonNode current = rootDocument;
        String[] segments = ref.substring(2).split("/");
        for (String segment : segments) {
            current = current.path(segment);
            if (current.isMissingNode()) {
                return null;
            }
        }
        return current;
    }

    private void resolveObjectField(JsonNode rootDocument, ObjectNode objectNode, String fieldName, Set<String> visitedRefs) {
        JsonNode fieldNode = objectNode.path(fieldName);
        if (!fieldNode.isMissingNode() && !fieldNode.isNull()) {
            objectNode.set(fieldName, resolveSchemaNode(rootDocument, fieldNode, new HashSet<>(visitedRefs)));
        }
    }

    private void resolveArrayField(JsonNode rootDocument, ObjectNode objectNode, String fieldName, Set<String> visitedRefs) {
        JsonNode fieldNode = objectNode.path(fieldName);
        if (!fieldNode.isArray()) {
            return;
        }
        ArrayNode resolvedArray = objectMapper.createArrayNode();
        for (JsonNode item : fieldNode) {
            resolvedArray.add(resolveSchemaNode(rootDocument, item, new HashSet<>(visitedRefs)));
        }
        objectNode.set(fieldName, resolvedArray);
    }

    /**
     * 合并 `allOf` 中的多个 schema。
     *
     * <p>这里主要合并对象字段、required 列表和其余可直接覆盖的属性，
     * 让最终导入结果更接近一个完整 DTO 定义。
     *
     * @param rootDocument OpenAPI 根文档
     * @param allOfNode allOf 数组
     * @param visitedRefs 已访问引用
     * @return 合并后的对象 schema
     */
    private ObjectNode mergeAllOfSchemas(JsonNode rootDocument, JsonNode allOfNode, Set<String> visitedRefs) {
        ObjectNode mergedNode = objectMapper.createObjectNode();
        ObjectNode mergedProperties = objectMapper.createObjectNode();
        ArrayNode mergedRequired = objectMapper.createArrayNode();

        for (JsonNode item : allOfNode) {
            JsonNode resolvedItem = resolveSchemaNode(rootDocument, item, new HashSet<>(visitedRefs));
            if (!(resolvedItem instanceof ObjectNode resolvedObject)) {
                continue;
            }

            JsonNode propertiesNode = resolvedObject.path("properties");
            if (propertiesNode.isObject()) {
                Iterator<Map.Entry<String, JsonNode>> propertyFields = propertiesNode.fields();
                while (propertyFields.hasNext()) {
                    Map.Entry<String, JsonNode> property = propertyFields.next();
                    mergedProperties.set(property.getKey(), property.getValue());
                }
            }

            JsonNode requiredNode = resolvedObject.path("required");
            if (requiredNode.isArray()) {
                for (JsonNode requiredItem : requiredNode) {
                    if (!containsTextNode(mergedRequired, requiredItem.asText())) {
                        mergedRequired.add(requiredItem.asText());
                    }
                }
            }

            Iterator<Map.Entry<String, JsonNode>> fields = resolvedObject.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();
                if ("properties".equals(field.getKey()) || "required".equals(field.getKey())) {
                    continue;
                }
                mergedNode.set(field.getKey(), field.getValue());
            }
        }

        if (!mergedProperties.isEmpty()) {
            mergedNode.set("properties", mergedProperties);
            if (!mergedNode.has("type")) {
                mergedNode.put("type", "object");
            }
        }
        if (!mergedRequired.isEmpty()) {
            mergedNode.set("required", mergedRequired);
        }
        return mergedNode;
    }

    private boolean containsTextNode(ArrayNode arrayNode, String expectedValue) {
        for (JsonNode item : arrayNode) {
            if (expectedValue.equals(item.asText())) {
                return true;
            }
        }
        return false;
    }

    private JsonNode extractPrimaryResponse(JsonNode operationNode) {
        JsonNode responsesNode = operationNode.path("responses");
        if (!responsesNode.isObject()) {
            return null;
        }
        for (String statusCode : List.of("200", "201", "default")) {
            JsonNode response = responsesNode.path(statusCode);
            if (!response.isMissingNode()) {
                return response;
            }
        }
        Iterator<Map.Entry<String, JsonNode>> iterator = responsesNode.fields();
        return iterator.hasNext() ? iterator.next().getValue() : null;
    }

    private Map<String, Object> readMap(String json) {
        if (!StringUtils.hasText(json)) {
            return new LinkedHashMap<>();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (JsonProcessingException ex) {
            return new LinkedHashMap<>();
        }
    }

    private JsonNode readJsonTree(String json, String errorMessage) {
        try {
            return objectMapper.readTree(defaultIfBlank(json, "{}"));
        } catch (JsonProcessingException ex) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, errorMessage, ex);
        }
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value == null ? Map.of() : value);
        } catch (JsonProcessingException ex) {
            throw new BusinessException(ErrorCode.INTERNAL_ERROR, "JSON 序列化失败", ex);
        }
    }

    private String toJsonString(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return "{}";
        }
        return writeJson(objectMapper.convertValue(node, Object.class));
    }

    private Object parsePossiblyJson(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        try {
            return objectMapper.readValue(value, Object.class);
        } catch (JsonProcessingException ex) {
            return value;
        }
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (StringUtils.hasText(value)) {
                return value;
            }
        }
        return null;
    }

    private String defaultIfBlank(String value, String defaultValue) {
        return StringUtils.hasText(value) ? value : defaultValue;
    }

    private void requireText(String value, String message) {
        if (!StringUtils.hasText(value)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, message);
        }
    }
}
