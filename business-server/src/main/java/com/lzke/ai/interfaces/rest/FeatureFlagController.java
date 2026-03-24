package com.lzke.ai.interfaces.rest;

import com.lzke.ai.application.vo.ApiResponse;
import com.lzke.ai.service.FeatureFlagService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@Tag(name = "Feature Flags", description = "功能开关管理")
@RestController
@RequestMapping("/api/v1/feature-flags")
@RequiredArgsConstructor
public class FeatureFlagController {

    private final FeatureFlagService featureFlagService;

    @Operation(summary = "查询所有 Feature Flag 状态")
    @GetMapping
    public ApiResponse<Map<String, Object>> listFlags() {
        return ApiResponse.ok(featureFlagService.getAllFlags());
    }

    @Operation(summary = "查询单个 Feature Flag 是否启用")
    @GetMapping("/{flagName}")
    public ApiResponse<Boolean> checkFlag(
            @Parameter(description = "Flag 名称") @PathVariable String flagName,
            @Parameter(description = "用户 ID（可选）") @RequestParam(required = false) String userId) {
        boolean enabled = featureFlagService.isEnabled(flagName, userId);
        return ApiResponse.ok(enabled);
    }
}
