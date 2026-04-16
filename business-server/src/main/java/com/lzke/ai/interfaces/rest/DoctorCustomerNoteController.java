package com.lzke.ai.interfaces.rest;

import com.lzke.ai.application.workbench.DoctorWorkbenchApplicationService;
import com.lzke.ai.application.workbench.dto.DoctorCustomerNoteQueryRequest;
import com.lzke.ai.application.workbench.dto.DoctorCustomerNoteRequest;
import com.lzke.ai.domain.entity.DoctorCustomerNote;
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
 * 医生工作台客户便签控制器。
 */
@Tag(name = "医生工作台-客户便签", description = "维护员工针对客户的便签和标注信息")
@RestController
@RequestMapping("/bs/api/v1/doctor-workbench/customer-notes")
@RequiredArgsConstructor
public class DoctorCustomerNoteController {

    private final DoctorWorkbenchApplicationService doctorWorkbenchApplicationService;

    @Operation(summary = "分页查询客户便签", description = "按员工、客户身份证、关键字和状态分页查询客户便签")
    @PostMapping("/query")
    public ApiResponse<PageResult<DoctorCustomerNote>> listCustomerNotes(
            @RequestBody(required = false) DoctorCustomerNoteQueryRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.listCustomerNotes(request));
    }

    @Operation(summary = "查询客户便签详情", description = "根据主键查询单条客户便签")
    @GetMapping("/{id}")
    public ApiResponse<DoctorCustomerNote> getCustomerNote(
            @Parameter(description = "客户便签主键ID", required = true)
            @PathVariable String id
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.getCustomerNote(id));
    }

    @Operation(summary = "按员工和客户查询便签", description = "查询某个员工对某个客户维护的全部有效便签")
    @GetMapping("/by-customer")
    public ApiResponse<List<DoctorCustomerNote>> listCustomerNotesByCustomer(
            @Parameter(description = "客户身份证号", required = true)
            @RequestParam String customerIdCard
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.listCustomerNotesByCustomer(customerIdCard));
    }

    @Operation(summary = "新增客户便签", description = "新增某个员工对客户的便签")
    @PostMapping
    public ApiResponse<DoctorCustomerNote> createCustomerNote(@RequestBody DoctorCustomerNoteRequest request) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.createCustomerNote(request));
    }

    @Operation(summary = "更新客户便签", description = "根据主键更新客户便签")
    @PutMapping("/{id}")
    public ApiResponse<DoctorCustomerNote> updateCustomerNote(
            @Parameter(description = "客户便签主键ID", required = true)
            @PathVariable String id,
            @RequestBody DoctorCustomerNoteRequest request
    ) {
        return ApiResponse.ok(doctorWorkbenchApplicationService.updateCustomerNote(id, request));
    }

    @Operation(summary = "删除客户便签", description = "根据主键删除客户便签")
    @DeleteMapping("/{id}")
    public ApiResponse<Void> deleteCustomerNote(
            @Parameter(description = "客户便签主键ID", required = true)
            @PathVariable String id
    ) {
        doctorWorkbenchApplicationService.deleteCustomerNote(id);
        return ApiResponse.ok();
    }
}
