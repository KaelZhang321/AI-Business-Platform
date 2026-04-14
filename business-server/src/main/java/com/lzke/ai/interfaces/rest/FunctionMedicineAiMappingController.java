package com.lzke.ai.interfaces.rest;

import com.lzke.ai.application.dto.FunctionMedicineAiMappingQueryRequest;
import com.lzke.ai.application.dto.FunctionMedicineAiMappingRequest;
import com.lzke.ai.application.recommend.FunctionMedicineAiMappingApplicationService;
import com.lzke.ai.domain.entity.FunctionMedicineAiMapping;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.PageResult;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 功能医学 AI 推荐方案映射控制器。
 */
@Tag(name = "功能医学 AI 推荐方案映射", description = "维护功能医学推荐方案与指标之间的映射关系")
@RestController
@RequestMapping("/api/v1/function-medicine-ai-mappings")
@RequiredArgsConstructor
public class FunctionMedicineAiMappingController {

    private final FunctionMedicineAiMappingApplicationService functionMedicineAiMappingApplicationService;

    @Operation(summary = "分页查询映射列表")
    @PostMapping("/query")
    public ApiResponse<PageResult<FunctionMedicineAiMapping>> listMappings(
            @RequestBody(required = false) FunctionMedicineAiMappingQueryRequest request
    ) {
        return ApiResponse.ok(functionMedicineAiMappingApplicationService.listMappings(request));
    }

    @Operation(summary = "查询映射详情")
    @GetMapping("/{mappingId}")
    public ApiResponse<FunctionMedicineAiMapping> getMapping(@PathVariable String mappingId) {
        return ApiResponse.ok(functionMedicineAiMappingApplicationService.getMapping(mappingId));
    }

    @Operation(summary = "新增映射")
    @PostMapping
    public ApiResponse<FunctionMedicineAiMapping> createMapping(@RequestBody FunctionMedicineAiMappingRequest request) {
        return ApiResponse.ok(functionMedicineAiMappingApplicationService.createMapping(request));
    }

    @Operation(summary = "更新映射")
    @PutMapping("/{mappingId}")
    public ApiResponse<FunctionMedicineAiMapping> updateMapping(
            @PathVariable String mappingId,
            @RequestBody FunctionMedicineAiMappingRequest request
    ) {
        return ApiResponse.ok(functionMedicineAiMappingApplicationService.updateMapping(mappingId, request));
    }

    @Operation(summary = "删除映射")
    @DeleteMapping("/{mappingId}")
    public ApiResponse<Void> deleteMapping(@PathVariable String mappingId) {
        functionMedicineAiMappingApplicationService.deleteMapping(mappingId);
        return ApiResponse.ok();
    }
}
