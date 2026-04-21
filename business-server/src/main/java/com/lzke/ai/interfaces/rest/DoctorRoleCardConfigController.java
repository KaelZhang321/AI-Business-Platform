package com.lzke.ai.interfaces.rest;

import com.lzke.ai.application.workbench.DoctorWorkbenchApplicationService;
import com.lzke.ai.application.workbench.dto.DoctorRoleCardConfigQueryRequest;
import com.lzke.ai.application.workbench.dto.DoctorRoleCardConfigRequest;
import com.lzke.ai.domain.entity.DoctorRoleCardConfig;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.PageResult;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 医生工作台角色卡片配置控制器。
 */
@Tag(name = "医生工作台-角色卡片配置", description = "维护角色对应的工作台卡片分组和卡片配置")
@RestController
@RequestMapping("/bs/api/v1/doctor-workbench/role-card-configs")
@RequiredArgsConstructor
public class DoctorRoleCardConfigController {

    private final DoctorWorkbenchApplicationService doctorWorkbenchApplicationService;

    @Operation(summary = "分页查询角色卡片配置", description = "按角色、分组、卡片名称、状态等条件分页查询医生工作台卡片配置")
    @PostMapping("/query")
    public ApiResponse<PageResult<DoctorRoleCardConfig>> listRoleCardConfigs(
            @RequestBody(required = false) DoctorRoleCardConfigQueryRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.listRoleCardConfigs(request));
    }

    @Operation(summary = "查询角色卡片配置详情", description = "根据主键查询单条医生角色卡片配置")
    @GetMapping("/{id}")
    public ApiResponse<DoctorRoleCardConfig> getRoleCardConfig(
            @Parameter(description = "角色卡片配置主键ID", required = true)
            @PathVariable String id
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.getRoleCardConfig(id));
    }

    @Operation(summary = "按角色查询可用卡片", description = "查询某个角色当前可见且启用的卡片配置，前端可直接按分组渲染")
    @GetMapping("/by-role/{roleId}")
    public ApiResponse<List<DoctorRoleCardConfig>> listRoleCardConfigsByRole(
            @Parameter(description = "角色ID", required = true)
            @PathVariable String roleId
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.listRoleCardConfigsByRole(roleId));
    }

    @Operation(summary = "查询当前登录员工可用卡片", description = "根据当前登录员工角色查询启用且可见的卡片配置")
    @GetMapping("/mine")
    public ApiResponse<List<DoctorRoleCardConfig>> listRoleCardConfigsByCurrentUser(
            @Parameter(description = "应用编码，默认 AI-RND-WORKFLOW")
            @RequestParam(value = "appCode", required = false) String appCode
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.listRoleCardConfigsForCurrentUser(appCode));
    }

    @Operation(summary = "新增角色卡片配置", description = "为指定角色新增一张工作台卡片配置")
    @PostMapping
    public ApiResponse<DoctorRoleCardConfig> createRoleCardConfig(@RequestBody DoctorRoleCardConfigRequest request) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.createRoleCardConfig(request));
    }

    @Operation(summary = "更新角色卡片配置", description = "根据主键更新角色卡片配置")
    @PutMapping("/{id}")
    public ApiResponse<DoctorRoleCardConfig> updateRoleCardConfig(
            @Parameter(description = "角色卡片配置主键ID", required = true)
            @PathVariable String id,
            @RequestBody DoctorRoleCardConfigRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.updateRoleCardConfig(id, request));
    }

    @Operation(summary = "删除角色卡片配置", description = "根据主键删除角色卡片配置")
    @DeleteMapping("/{id}")
    public ApiResponse<Void> deleteRoleCardConfig(
            @Parameter(description = "角色卡片配置主键ID", required = true)
            @PathVariable String id
    ) {
        doctorWorkbenchApplicationService.deleteRoleCardConfig(id);
        return ApiResponse.ok();
    }
}
