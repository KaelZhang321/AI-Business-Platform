package com.lzke.ai.interfaces.rest;

import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.service.JsonRenderTestService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@Tag(name = "json-render 测试", description = "返回和动态编辑前端 json-render Spec")
@RestController
@RequestMapping("/api/v1/ui-spec/test")
@RequiredArgsConstructor
public class JsonRenderTestController {

    private final JsonRenderTestService jsonRenderTestService;

    @Operation(summary = "获取测试 Spec", description = "返回前端 @json-render/react 可直接渲染的 JSON")
    @GetMapping
    public ApiResponse<Map<String, Object>> getTestSpec() {
        return ApiResponse.ok(jsonRenderTestService.getCurrentSpec());
    }

    @Operation(summary = "整份替换测试 Spec", description = "用一整份 json-render Spec 覆盖当前测试数据")
    @PutMapping
    public ApiResponse<Map<String, Object>> replaceTestSpec(@RequestBody Map<String, Object> spec) {
        return ApiResponse.ok(jsonRenderTestService.replaceSpec(spec));
    }

    @Operation(summary = "按元素动态修改 Spec", description = "局部更新某个 element 的 type、props 或 children")
    @PatchMapping("/elements/{elementId}")
    public ApiResponse<Map<String, Object>> updateElement(
            @Parameter(description = "element ID，例如 page、tableCard") @PathVariable String elementId,
            @RequestBody Map<String, Object> patch) {
        return ApiResponse.ok(jsonRenderTestService.updateElement(elementId, patch));
    }

    @Operation(summary = "重置测试 Spec", description = "恢复为服务内置的默认 json-render 示例")
    @PostMapping("/reset")                                                       
    public ApiResponse<Map<String, Object>> resetSpec() {
        return ApiResponse.ok(jsonRenderTestService.resetSpec());
    }
}
