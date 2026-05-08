package com.lzke.ai.interfaces.rest;

import com.lzke.ai.application.workbench.DoctorWorkbenchApplicationService;
import com.lzke.ai.application.workbench.dto.DoctorCardGroupQueryRequest;
import com.lzke.ai.application.workbench.dto.DoctorCardGroupRelationQueryRequest;
import com.lzke.ai.application.workbench.dto.DoctorCardGroupRelationRequest;
import com.lzke.ai.application.workbench.dto.DoctorCardGroupRequest;
import com.lzke.ai.domain.entity.DoctorCardGroup;
import com.lzke.ai.domain.entity.DoctorCardGroupRelation;
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
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 医生工作台分组及分组卡片关系控制器。
 */
@Tag(name = "医生工作台-卡片分组", description = "维护卡片分组以及分组和卡片的关系")
@RestController
@RequestMapping("/bs/api/v1/doctor-workbench")
@RequiredArgsConstructor
public class DoctorCardGroupController {

    private final DoctorWorkbenchApplicationService doctorWorkbenchApplicationService;

    @Operation(summary = "分页查询卡片分组", description = "按角色、分组名称和状态分页查询卡片分组")
    @PostMapping("/card-groups/query")
    public ApiResponse<PageResult<DoctorCardGroup>> listCardGroups(
            @RequestBody(required = false) DoctorCardGroupQueryRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.listCardGroups(request));
    }

    @Operation(summary = "查询卡片分组详情", description = "根据主键查询单条卡片分组")
    @GetMapping("/card-groups/{id}")
    public ApiResponse<DoctorCardGroup> getCardGroup(
            @Parameter(description = "卡片分组主键ID", required = true)
            @PathVariable String id
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.getCardGroup(id));
    }

    @Operation(summary = "新增卡片分组", description = "新增一个卡片分组，创建人与更新人由后端自动取当前登录用户")
    @PostMapping("/card-groups")
    public ApiResponse<DoctorCardGroup> createCardGroup(@RequestBody DoctorCardGroupRequest request) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.createCardGroup(request));
    }

    @Operation(summary = "更新卡片分组", description = "根据主键更新卡片分组，更新人由后端自动取当前登录用户")
    @PutMapping("/card-groups/{id}")
    public ApiResponse<DoctorCardGroup> updateCardGroup(
            @Parameter(description = "卡片分组主键ID", required = true)
            @PathVariable String id,
            @RequestBody DoctorCardGroupRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.updateCardGroup(id, request));
    }

    @Operation(summary = "删除卡片分组", description = "根据主键删除卡片分组")
    @DeleteMapping("/card-groups/{id}")
    public ApiResponse<Void> deleteCardGroup(
            @Parameter(description = "卡片分组主键ID", required = true)
            @PathVariable String id
    ) {
        doctorWorkbenchApplicationService.deleteCardGroup(id);
        return ApiResponse.ok();
    }

    @Operation(summary = "分页查询分组卡片关系", description = "按分组、卡片配置和状态分页查询分组卡片关系")
    @PostMapping("/card-group-relations/query")
    public ApiResponse<PageResult<DoctorCardGroupRelation>> listCardGroupRelations(
            @RequestBody(required = false) DoctorCardGroupRelationQueryRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.listCardGroupRelations(request));
    }

    @Operation(summary = "查询分组卡片关系详情", description = "根据主键查询单条分组卡片关系")
    @GetMapping("/card-group-relations/{id}")
    public ApiResponse<DoctorCardGroupRelation> getCardGroupRelation(
            @Parameter(description = "分组卡片关系主键ID", required = true)
            @PathVariable String id
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.getCardGroupRelation(id));
    }

    @Operation(summary = "按分组查询卡片关系", description = "查询某个分组下全部有效卡片关系")
    @GetMapping("/card-group-relations/by-group/{groupId}")
    public ApiResponse<List<DoctorCardGroupRelation>> listCardGroupRelationsByGroup(
            @Parameter(description = "卡片分组ID", required = true)
            @PathVariable String groupId
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.listCardGroupRelationsByGroup(groupId));
    }

    @Operation(summary = "新增分组卡片关系", description = "新增一个分组和卡片配置之间的关系")
    @PostMapping("/card-group-relations")
    public ApiResponse<DoctorCardGroupRelation> createCardGroupRelation(@RequestBody DoctorCardGroupRelationRequest request) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.createCardGroupRelation(request));
    }

    @Operation(summary = "更新分组卡片关系", description = "根据主键更新分组卡片关系")
    @PutMapping("/card-group-relations/{id}")
    public ApiResponse<DoctorCardGroupRelation> updateCardGroupRelation(
            @Parameter(description = "分组卡片关系主键ID", required = true)
            @PathVariable String id,
            @RequestBody DoctorCardGroupRelationRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.updateCardGroupRelation(id, request));
    }

    @Operation(summary = "删除分组卡片关系", description = "根据主键删除分组卡片关系")
    @DeleteMapping("/card-group-relations/{id}")
    public ApiResponse<Void> deleteCardGroupRelation(
            @Parameter(description = "分组卡片关系主键ID", required = true)
            @PathVariable String id
    ) {
        doctorWorkbenchApplicationService.deleteCardGroupRelation(id);
        return ApiResponse.ok();
    }
}
