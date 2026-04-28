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
import com.lzke.ai.application.dto.UiCardEndpointBindRequest;
import com.lzke.ai.application.dto.UiCardRequest;
import com.lzke.ai.application.dto.UiJsonRenderInvokeRequest;
import com.lzke.ai.application.dto.UiJsonRenderInvokeResponse;
import com.lzke.ai.application.dto.UiJsonRenderSubmitRequest;
import com.lzke.ai.application.dto.UiJsonRenderSubmitResponse;
import com.lzke.ai.application.dto.UiApiSourceRequest;
import com.lzke.ai.application.dto.UiApiTestRequest;
import com.lzke.ai.application.dto.UiApiTestResponse;
import com.lzke.ai.application.dto.UiBuilderAuthTypeResponse;
import com.lzke.ai.application.dto.UiBuilderNodeTypeResponse;
import com.lzke.ai.application.dto.UiBuilderOverviewResponse;
import com.lzke.ai.application.dto.UiOpenApiImportRequest;
import com.lzke.ai.application.ui.UiBuilderApplicationService;
import com.lzke.ai.domain.entity.UiApiEndpoint;
import com.lzke.ai.domain.entity.UiApiEndpointRole;
import com.lzke.ai.domain.entity.SemanticFieldAlias;
import com.lzke.ai.domain.entity.SemanticFieldDict;
import com.lzke.ai.domain.entity.SemanticFieldValueMap;
import com.lzke.ai.domain.entity.UiApiSource;
import com.lzke.ai.domain.entity.UiApiTag;
import com.lzke.ai.domain.entity.UiApiFlowLog;
import com.lzke.ai.domain.entity.UiApiTestLog;
import com.lzke.ai.domain.entity.UiCard;
import com.lzke.ai.domain.entity.UiCardEndpointRelation;
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
 *     <li>卡片与接口关系配置</li>
 *     <li>运行时渲染与调用日志查询</li>
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
            @RequestParam(required = false) String name,
            @RequestParam(required = false) String path,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) Boolean untagged
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.listEndpointsBySource(sourceId, query, tagId, name, path, status, untagged));
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
     * 按接口定义发起真实调用，并把接口响应和 json-render 一起返回。
     */
    @PostMapping("/runtime/endpoints/{endpointId}/render")
    public ApiResponse<UiJsonRenderInvokeResponse> invokeEndpointAsJsonRender(
            @PathVariable String endpointId,
            @RequestBody(required = false) UiJsonRenderInvokeRequest request
    ) {
        Long userId = AuthUtil.getUserId();
        if (request == null) {
            request = new UiJsonRenderInvokeRequest();
        }
        if (userId != null) {
            request.setCreatedBy(String.valueOf(userId));
        }
        return ApiResponse.ok(uiBuilderApplicationService.invokeEndpointAsJsonRender(endpointId, request));
    }

    /**
     * 按标准语义字段值驱动多个接口完成表单提交。
     */
    @PostMapping("/runtime/forms/submit")
    public ApiResponse<UiJsonRenderSubmitResponse> submitJsonRenderForm(
            @RequestBody UiJsonRenderSubmitRequest request
    ) {
        Long userId = AuthUtil.getUserId();
        if (userId != null && !org.springframework.util.StringUtils.hasText(request.getCreatedBy())) {
            request.setCreatedBy(String.valueOf(userId));
        }
        return ApiResponse.ok(uiBuilderApplicationService.submitJsonRenderForm(request));
    }

    /**
     * 分页查询运行时调用日志。
     */
    @GetMapping("/flow-logs")
    public ApiResponse<PageResult<UiApiFlowLog>> listFlowLogs(
            @Valid PageQuery query,
            @RequestParam(required = false) String flowNum,
            @RequestParam(required = false) String requestUrl,
            @RequestParam(required = false) String createdBy,
            @RequestParam(required = false) String invokeStatus
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.listFlowLogs(query, flowNum, requestUrl, createdBy, invokeStatus));
    }

    /**
     * 分页查询卡片。
     */
    @GetMapping("/cards")
    public ApiResponse<PageResult<UiCard>> listCards(
            @Valid PageQuery query,
            @RequestParam(required = false) String name,
            @RequestParam(required = false) String status
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.listCards(query, name, status));
    }

    /**
     * 创建卡片。
     */
    @PostMapping("/cards")
    public ApiResponse<UiCard> createCard(@RequestBody UiCardRequest request) {
        Long userId = AuthUtil.getUserId();
        if (userId != null && !org.springframework.util.StringUtils.hasText(request.getCreatedBy())) {
            request.setCreatedBy(String.valueOf(userId));
        }
        return ApiResponse.ok(uiBuilderApplicationService.createCard(request));
    }

    /**
     * 更新卡片。
     */
    @PutMapping("/cards/{cardId}")
    public ApiResponse<UiCard> updateCard(@PathVariable String cardId, @RequestBody UiCardRequest request) {
        Long userId = AuthUtil.getUserId();
        if (userId != null && !org.springframework.util.StringUtils.hasText(request.getCreatedBy())) {
            request.setCreatedBy(String.valueOf(userId));
        }
        return ApiResponse.ok(uiBuilderApplicationService.updateCard(cardId, request));
    }

    /**
     * 删除卡片。
     */
    @DeleteMapping("/cards/{cardId}")
    public ApiResponse<Void> deleteCard(@PathVariable String cardId) {
        uiBuilderApplicationService.deleteCard(cardId);
        return ApiResponse.ok();
    }

    /**
     * 查询卡片关联的接口。
     */
    @GetMapping("/cards/{cardId}/endpoint-relations")
    public ApiResponse<PageResult<UiCardEndpointRelation>> listCardEndpointRelations(
            @PathVariable String cardId,
            @Valid PageQuery query
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.listCardEndpointRelations(cardId, query));
    }

    /**
     * 批量关联接口到卡片。
     */
    @PostMapping("/cards/{cardId}/endpoint-relations")
    public ApiResponse<java.util.List<UiCardEndpointRelation>> bindCardEndpointRelations(
            @PathVariable String cardId,
            @RequestBody UiCardEndpointBindRequest request
    ) {
        return ApiResponse.ok(uiBuilderApplicationService.bindCardEndpointRelations(cardId, request));
    }

    /**
     * 删除卡片接口关系。
     */
    @DeleteMapping("/cards/{cardId}/endpoint-relations/{relationId}")
    public ApiResponse<Void> deleteCardEndpointRelation(
            @PathVariable String cardId,
            @PathVariable String relationId
    ) {
        uiBuilderApplicationService.deleteCardEndpointRelation(cardId, relationId);
        return ApiResponse.ok();
    }
}
