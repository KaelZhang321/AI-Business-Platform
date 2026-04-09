package com.lzke.ai.interfaces.rest;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.lecz.service.tools.core.utils.AuthUtil;
import com.lzke.ai.application.dto.PageQuery;
import com.lzke.ai.application.dto.SemanticFieldAliasRequest;
import com.lzke.ai.application.dto.SemanticFieldDictRequest;
import com.lzke.ai.application.dto.SemanticFieldValueMapRequest;
import com.lzke.ai.application.dto.UiApiEndpointRequest;
import com.lzke.ai.application.dto.UiApiEndpointRoleBindRequest;
import com.lzke.ai.application.dto.UiApiInvokeRequest;
import com.lzke.ai.application.dto.UiApiSourceRequest;
import com.lzke.ai.application.dto.UiApiTestRequest;
import com.lzke.ai.application.dto.UiApiTestResponse;
import com.lzke.ai.application.dto.UiBuilderAuthTypeResponse;
import com.lzke.ai.application.dto.UiBuilderNodeTypeResponse;
import com.lzke.ai.application.dto.UiBuilderOverviewResponse;
import com.lzke.ai.application.dto.UiBuilderPageDetailResponse;
import com.lzke.ai.application.dto.UiNodeBindingRequest;
import com.lzke.ai.application.dto.UiOpenApiImportRequest;
import com.lzke.ai.application.dto.UiPageNodeRequest;
import com.lzke.ai.application.dto.UiPagePreviewResponse;
import com.lzke.ai.application.dto.UiPageRequest;
import com.lzke.ai.application.dto.UiProjectRequest;
import com.lzke.ai.application.ui.UiBuilderApplicationService;
import com.lzke.ai.domain.entity.UiApiEndpoint;
import com.lzke.ai.domain.entity.UiApiEndpointRole;
import com.lzke.ai.domain.entity.SemanticFieldAlias;
import com.lzke.ai.domain.entity.SemanticFieldDict;
import com.lzke.ai.domain.entity.SemanticFieldValueMap;
import com.lzke.ai.domain.entity.UiApiSource;
import com.lzke.ai.domain.entity.UiApiTag;
import com.lzke.ai.domain.entity.UiApiTestLog;
import com.lzke.ai.domain.entity.UiNodeBinding;
import com.lzke.ai.domain.entity.UiPage;
import com.lzke.ai.domain.entity.UiPageNode;
import com.lzke.ai.domain.entity.UiProject;
import com.lzke.ai.domain.entity.UiSpecVersion;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.PageResult;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;

/**
 * UI Builder REST 控制器。
 *
 * <p>该控制器面向前端工作台暴露一整套配置接口，覆盖：
 *
 * <ul>
 *     <li>接口源与接口定义管理</li>
 *     <li>OpenAPI/Swagger 导入与接口联调</li>
 *     <li>项目、页面、节点、字段绑定配置</li>
 *     <li>页面预览与版本发布</li>
 * </ul>
 *
 * <p>控制器本身只承担 HTTP 协议转换职责，核心业务逻辑统一下沉到
 * {@link UiBuilderApplicationService}。
 */
@Tag(name = "UI Builder", description = "接口文档转 json-render 的配置中心")
@RestController
@RequestMapping("/api/v1/ui-builder")
@RequiredArgsConstructor
public class UiBuilderController {

    private final UiBuilderApplicationService uiBuilderApplicationService;

    @Operation(summary = "获取模块概览", description = "返回 UI Builder 的功能结构、节点类型和表模型设计")
    @GetMapping("/overview")
    public ApiResponse<UiBuilderOverviewResponse> getOverview() {
        return ApiResponse.ok(uiBuilderApplicationService.getOverview());
    }

    @Operation(summary = "获取组件类型", description = "返回当前前端支持的 json-render 节点类型")
    @GetMapping("/component-types")
    public ApiResponse<PageResult<UiBuilderNodeTypeResponse>> getComponentTypes(@Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.getNodeTypes(query));
    }

    @Operation(summary = "获取认证类型", description = "返回三方接口源可选的认证方式")
    @GetMapping("/auth-types")
    public ApiResponse<PageResult<UiBuilderAuthTypeResponse>> getAuthTypes(@Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.getAuthTypes(query));
    }

    /**
     * 查询语义字段字典。
     */
    @GetMapping("/semantic-fields")
    public ApiResponse<PageResult<SemanticFieldDict>> listSemanticFields(@Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.listSemanticFields(query));
    }

    /**
     * 创建语义字段字典。
     */
    @PostMapping("/semantic-fields")
    public ApiResponse<SemanticFieldDict> createSemanticField(@RequestBody SemanticFieldDictRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.createSemanticField(request));
    }

    /**
     * 更新语义字段字典。
     */
    @PutMapping("/semantic-fields/{dictId}")
    public ApiResponse<SemanticFieldDict> updateSemanticField(
            @PathVariable Long dictId,
            @RequestBody SemanticFieldDictRequest request
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.updateSemanticField(dictId, request));
    }

    /**
     * 删除语义字段字典。
     */
    @DeleteMapping("/semantic-fields/{dictId}")
    public ApiResponse<Void> deleteSemanticField(@PathVariable Long dictId) {
        uiBuilderApplicationService.deleteSemanticField(dictId);
        return ApiResponse.ok();
    }

    /**
     * 查询标准字段下的别名映射。
     */
    @GetMapping("/semantic-fields/{standardKey}/aliases")
    public ApiResponse<PageResult<SemanticFieldAlias>> listSemanticFieldAliases(
            @PathVariable String standardKey,
            @Valid PageQuery query
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.listSemanticFieldAliases(standardKey, query));
    }

    /**
     * 创建别名映射。
     */
    @PostMapping("/semantic-field-aliases")
    public ApiResponse<SemanticFieldAlias> createSemanticFieldAlias(@RequestBody SemanticFieldAliasRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.createSemanticFieldAlias(request));
    }

    /**
     * 更新别名映射。
     */
    @PutMapping("/semantic-field-aliases/{aliasId}")
    public ApiResponse<SemanticFieldAlias> updateSemanticFieldAlias(
            @PathVariable Long aliasId,
            @RequestBody SemanticFieldAliasRequest request
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.updateSemanticFieldAlias(aliasId, request));
    }

    /**
     * 删除别名映射。
     */
    @DeleteMapping("/semantic-field-aliases/{aliasId}")
    public ApiResponse<Void> deleteSemanticFieldAlias(@PathVariable Long aliasId) {
        uiBuilderApplicationService.deleteSemanticFieldAlias(aliasId);
        return ApiResponse.ok();
    }

    /**
     * 查询标准字段下的值映射。
     */
    @GetMapping("/semantic-fields/{standardKey}/value-maps")
    public ApiResponse<PageResult<SemanticFieldValueMap>> listSemanticFieldValueMaps(
            @PathVariable String standardKey,
            @Valid PageQuery query
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.listSemanticFieldValueMaps(standardKey, query));
    }

    /**
     * 创建值映射。
     */
    @PostMapping("/semantic-field-value-maps")
    public ApiResponse<SemanticFieldValueMap> createSemanticFieldValueMap(@RequestBody SemanticFieldValueMapRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.createSemanticFieldValueMap(request));
    }

    /**
     * 更新值映射。
     */
    @PutMapping("/semantic-field-value-maps/{valueMapId}")
    public ApiResponse<SemanticFieldValueMap> updateSemanticFieldValueMap(
            @PathVariable Long valueMapId,
            @RequestBody SemanticFieldValueMapRequest request
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.updateSemanticFieldValueMap(valueMapId, request));
    }

    /**
     * 删除值映射。
     */
    @DeleteMapping("/semantic-field-value-maps/{valueMapId}")
    public ApiResponse<Void> deleteSemanticFieldValueMap(@PathVariable Long valueMapId) {
        uiBuilderApplicationService.deleteSemanticFieldValueMap(valueMapId);
        return ApiResponse.ok();
    }

    /**
     * 查询接口源列表。
     */
    @GetMapping("/sources")
    public ApiResponse<PageResult<UiApiSource>> listSources(@Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.listSources(query));
    }

    /**
     * 查询接口源下的标签列表。
     */
    @GetMapping("/sources/{sourceId}/tags")
    public ApiResponse<PageResult<UiApiTag>> listTagsBySource(@PathVariable String sourceId, @Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.listTagsBySource(sourceId, query));
    }

    /**
     * 创建接口源。
     */
    @PostMapping("/sources")
    public ApiResponse<UiApiSource> createSource(@RequestBody UiApiSourceRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.createSource(request));
    }

    /**
     * 更新接口源。
     */
    @PutMapping("/sources/{sourceId}")
    public ApiResponse<UiApiSource> updateSource(@PathVariable String sourceId, @RequestBody UiApiSourceRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.updateSource(sourceId, request));
    }

    /**
     * 删除接口源。
     */
    @DeleteMapping("/sources/{sourceId}")
    public ApiResponse<Void> deleteSource(@PathVariable String sourceId) {
        uiBuilderApplicationService.deleteSource(sourceId);
        return ApiResponse.ok();
    }

    /**
     * 查询接口源下的接口定义列表。
     */
    @GetMapping("/sources/{sourceId}/endpoints")
    public ApiResponse<PageResult<UiApiEndpoint>> listEndpointsBySource(
            @PathVariable String sourceId,
            @Valid PageQuery query,
            @RequestParam(required = false) String tagId,
            @RequestParam(required = false) Boolean untagged
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.listEndpointsBySource(sourceId, query, tagId, untagged));
    }

    /**
     * 导入 OpenAPI/Swagger 文档。
     *
     * <p>请求体支持直接传文档内容，也支持传 Swagger 地址。
     */
    @PostMapping("/sources/{sourceId}/import-openapi")
    public ApiResponse<PageResult<UiApiEndpoint>> importOpenApi(
            @PathVariable String sourceId,
            @RequestBody UiOpenApiImportRequest request,
            @Valid PageQuery query
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.importOpenApi(sourceId, request, query));
    }

    /**
     * 查询单个接口定义详情。
     */
    @GetMapping("/endpoints/{endpointId}")
    public ApiResponse<UiApiEndpoint> getEndpoint(@PathVariable String endpointId) {
        return ApiResponse.ok(uiBuilderApplicationService.getEndpoint(endpointId));
    }

    /**
     * 查询某个接口定义的最近联调日志。
     */
    @GetMapping("/endpoints/{endpointId}/test-logs")
    public ApiResponse<PageResult<UiApiTestLog>> listTestLogs(@PathVariable String endpointId, @Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.listTestLogs(endpointId, query));
    }

    /**
     * 分页查询接口与角色关系。
     */
    @GetMapping("/endpoint-role-relations")
    public ApiResponse<PageResult<UiApiEndpointRole>> listEndpointRoleRelations(
            @Valid PageQuery query,
            @RequestParam(required = false) String roleId
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.listEndpointRoleRelations(roleId, query));
    }

    /**
     * 批量把接口定义关联到某个角色。
     */
    @PostMapping("/endpoint-role-relations")
    public ApiResponse<java.util.List<UiApiEndpointRole>> bindEndpointRoleRelations(
            @RequestBody UiApiEndpointRoleBindRequest request
    ) {
        Long userId = AuthUtil.getUserId();
        if (userId != null && !org.springframework.util.StringUtils.hasText(request.getCreatedBy())) {
            request.setCreatedBy(String.valueOf(userId));
        }
        return ApiResponse.ok(uiBuilderApplicationService.bindEndpointRoleRelations(request));
    }

    /**
     * 删除单条接口与角色关系。
     */
    @DeleteMapping("/endpoint-role-relations/{relationId}")
    public ApiResponse<Void> deleteEndpointRoleRelation(@PathVariable String relationId) {
        uiBuilderApplicationService.deleteEndpointRoleRelation(relationId);
        return ApiResponse.ok();
    }

    /**
     * 创建接口定义。
     */
    @PostMapping("/endpoints")
    public ApiResponse<UiApiEndpoint> createEndpoint(@RequestBody UiApiEndpointRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.createEndpoint(request));
    }

    /**
     * 更新接口定义。
     */
    @PutMapping("/endpoints/{endpointId}")
    public ApiResponse<UiApiEndpoint> updateEndpoint(@PathVariable String endpointId, @RequestBody UiApiEndpointRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.updateEndpoint(endpointId, request));
    }

    /**
     * 删除接口定义。
     */
    @DeleteMapping("/endpoints/{endpointId}")
    public ApiResponse<Void> deleteEndpoint(@PathVariable String endpointId) {
        uiBuilderApplicationService.deleteEndpoint(endpointId);
        return ApiResponse.ok();
    }

    /**
     * 发起一次接口联调。
     */
    @PostMapping("/endpoints/{endpointId}/test")
    public ApiResponse<UiApiTestResponse> testEndpoint(@PathVariable String endpointId, @RequestBody(required = false) UiApiTestRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.testEndpoint(endpointId, request));
    }

    /**
     * 按接口定义发起一次运行时真实调用。
     */
    @PostMapping("/runtime/endpoints/{endpointId}/invoke")
    public ApiResponse<Object> invokeEndpoint(
            @PathVariable String endpointId,
            @RequestBody(required = false) UiApiInvokeRequest request
    ) {
    	Long userId = AuthUtil.getUserId();
    	if(userId != null) {
    		request.setCreatedBy(userId+"");
    	}
        return ApiResponse.ok(uiBuilderApplicationService.invokeEndpoint(endpointId, request));
    }

    /**
     * 查询项目列表。
     */
    @GetMapping("/projects")
    public ApiResponse<PageResult<UiProject>> listProjects(@Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.listProjects(query));
    }

    /**
     * 创建项目。
     */
    @PostMapping("/projects")
    public ApiResponse<UiProject> createProject(@RequestBody UiProjectRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.createProject(request));
    }

    /**
     * 更新项目。
     */
    @PutMapping("/projects/{projectId}")
    public ApiResponse<UiProject> updateProject(@PathVariable String projectId, @RequestBody UiProjectRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.updateProject(projectId, request));
    }

    /**
     * 删除项目。
     */
    @DeleteMapping("/projects/{projectId}")
    public ApiResponse<Void> deleteProject(@PathVariable String projectId) {
        uiBuilderApplicationService.deleteProject(projectId);
        return ApiResponse.ok();
    }

    /**
     * 查询项目下的页面列表。
     */
    @GetMapping("/projects/{projectId}/pages")
    public ApiResponse<PageResult<UiPage>> listPages(@PathVariable String projectId, @Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.listPages(projectId, query));
    }

    /**
     * 创建页面。
     */
    @PostMapping("/projects/{projectId}/pages")
    public ApiResponse<UiPage> createPage(@PathVariable String projectId, @RequestBody UiPageRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.createPage(projectId, request));
    }

    /**
     * 获取页面详情。
     */
    @GetMapping("/pages/{pageId}")
    public ApiResponse<UiBuilderPageDetailResponse> getPageDetail(@PathVariable String pageId) {
        return ApiResponse.ok(uiBuilderApplicationService.getPageDetail(pageId));
    }

    /**
     * 更新页面。
     */
    @PutMapping("/pages/{pageId}")
    public ApiResponse<UiPage> updatePage(@PathVariable String pageId, @RequestBody UiPageRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.updatePage(pageId, request));
    }

    /**
     * 删除页面。
     */
    @DeleteMapping("/pages/{pageId}")
    public ApiResponse<Void> deletePage(@PathVariable String pageId) {
        uiBuilderApplicationService.deletePage(pageId);
        return ApiResponse.ok();
    }

    /**
     * 查询页面节点列表。
     */
    @GetMapping("/pages/{pageId}/nodes")
    public ApiResponse<PageResult<UiPageNode>> listNodes(@PathVariable String pageId, @Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.listNodes(pageId, query));
    }

    /**
     * 创建页面节点。
     */
    @PostMapping("/pages/{pageId}/nodes")
    public ApiResponse<UiPageNode> createNode(@PathVariable String pageId, @RequestBody UiPageNodeRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.createNode(pageId, request));
    }

    /**
     * 生成页面预览 spec。
     */
    @GetMapping("/pages/{pageId}/preview")
    public ApiResponse<UiPagePreviewResponse> previewPage(@PathVariable String pageId) {
        return ApiResponse.ok(uiBuilderApplicationService.previewPage(pageId));
    }

    /**
     * 查询页面版本列表。
     */
    @GetMapping("/pages/{pageId}/versions")
    public ApiResponse<PageResult<UiSpecVersion>> listVersions(@PathVariable String pageId, @Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.listVersions(pageId, query));
    }

    /**
     * 发布页面新版本。
     */
    @PostMapping("/pages/{pageId}/publish")
    public ApiResponse<UiSpecVersion> publishPage(@PathVariable String pageId) {
        return ApiResponse.ok(uiBuilderApplicationService.publishPage(pageId, "system"));
    }

    /**
     * 更新节点。
     */
    @PutMapping("/nodes/{nodeId}")
    public ApiResponse<UiPageNode> updateNode(@PathVariable String nodeId, @RequestBody UiPageNodeRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.updateNode(nodeId, request));
    }

    /**
     * 删除节点。
     */
    @DeleteMapping("/nodes/{nodeId}")
    public ApiResponse<Void> deleteNode(@PathVariable String nodeId) {
        uiBuilderApplicationService.deleteNode(nodeId);
        return ApiResponse.ok();
    }

    /**
     * 查询节点绑定列表。
     */
    @GetMapping("/nodes/{nodeId}/bindings")
    public ApiResponse<PageResult<UiNodeBinding>> listBindings(@PathVariable String nodeId, @Valid PageQuery query) {
        return ApiResponse.ok(uiBuilderApplicationService.listBindings(nodeId, query));
    }

    /**
     * 创建字段绑定。
     */
    @PostMapping("/nodes/{nodeId}/bindings")
    public ApiResponse<UiNodeBinding> createBinding(@PathVariable String nodeId, @RequestBody UiNodeBindingRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.createBinding(nodeId, request));
    }

    /**
     * 更新字段绑定。
     */
    @PutMapping("/bindings/{bindingId}")
    public ApiResponse<UiNodeBinding> updateBinding(@PathVariable String bindingId, @RequestBody UiNodeBindingRequest request) {
        return ApiResponse.ok(uiBuilderApplicationService.updateBinding(bindingId, request));
    }

    /**
     * 删除字段绑定。
     */
    @DeleteMapping("/bindings/{bindingId}")
    public ApiResponse<Void> deleteBinding(@PathVariable String bindingId) {
        uiBuilderApplicationService.deleteBinding(bindingId);
        return ApiResponse.ok();
    }
}
