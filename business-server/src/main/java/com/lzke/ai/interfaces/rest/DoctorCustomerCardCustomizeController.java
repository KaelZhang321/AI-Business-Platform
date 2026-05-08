package com.lzke.ai.interfaces.rest;

import com.lzke.ai.application.workbench.DoctorWorkbenchApplicationService;
import com.lzke.ai.application.workbench.dto.DoctorCustomerCardCustomizeQueryRequest;
import com.lzke.ai.application.workbench.dto.DoctorCustomerCardCustomizeRequest;
import com.lzke.ai.domain.entity.DoctorCustomerCardCustomize;
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
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 医生工作台客户定制卡片控制器。
 */
@Tag(name = "医生工作台-客户定制卡片", description = "维护员工针对客户保存的定制卡片信息")
@RestController
@RequestMapping("/bs/api/v1/doctor-workbench/customer-card-customizes")
@RequiredArgsConstructor
public class DoctorCustomerCardCustomizeController {

    private final DoctorWorkbenchApplicationService doctorWorkbenchApplicationService;

    @Operation(summary = "分页查询客户定制卡片", description = "按员工、客户身份证、收藏名称和状态分页查询客户定制卡片")
    @PostMapping("/query")
    public ApiResponse<PageResult<DoctorCustomerCardCustomize>> listCustomerCardCustomizes(
            @RequestBody(required = false) DoctorCustomerCardCustomizeQueryRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.listCustomerCardCustomizes(request));
    }

    @Operation(summary = "查询客户定制卡片详情", description = "根据主键查询单条客户定制卡片")
    @GetMapping("/{id}")
    public ApiResponse<DoctorCustomerCardCustomize> getCustomerCardCustomize(
            @Parameter(description = "客户定制卡片主键ID", required = true)
            @PathVariable String id
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.getCustomerCardCustomize(id));
    }

    @Operation(summary = "按员工和客户查询定制卡片", description = "查询某个员工对某个客户配置的全部有效定制卡片")
    @GetMapping("/by-customer")
    public ApiResponse<List<DoctorCustomerCardCustomize>> listCustomerCardCustomizesByCustomer(
            @Parameter(description = "客户身份证号", required = true)
            @RequestParam String customerIdCard
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.listCustomerCardCustomizesByCustomer(customerIdCard));
    }

    @Operation(summary = "新增客户定制卡片", description = "保存某个员工对某个客户的一套定制卡片")
    @PostMapping
    public ApiResponse<DoctorCustomerCardCustomize> createCustomerCardCustomize(
            @RequestBody DoctorCustomerCardCustomizeRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.createCustomerCardCustomize(request));
    }

    @Operation(summary = "更新客户定制卡片", description = "根据主键更新客户定制卡片")
    @PutMapping("/{id}")
    public ApiResponse<DoctorCustomerCardCustomize> updateCustomerCardCustomize(
            @Parameter(description = "客户定制卡片主键ID", required = true)
            @PathVariable String id,
            @RequestBody DoctorCustomerCardCustomizeRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.updateCustomerCardCustomize(id, request));
    }

    @Operation(summary = "删除客户定制卡片", description = "根据主键删除客户定制卡片")
    @DeleteMapping("/{id}")
    public ApiResponse<Void> deleteCustomerCardCustomize(
            @Parameter(description = "客户定制卡片主键ID", required = true)
            @PathVariable String id
    ) {
        doctorWorkbenchApplicationService.deleteCustomerCardCustomize(id);
        return ApiResponse.ok();
    }
}
