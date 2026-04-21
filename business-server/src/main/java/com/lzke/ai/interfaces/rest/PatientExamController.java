package com.lzke.ai.interfaces.rest;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.lzke.ai.application.exam.PatientExamApplicationService;
import com.lzke.ai.application.exam.dto.MyCustomerListItemResponse;
import com.lzke.ai.application.exam.dto.MyCustomerListQueryRequest;
import com.lzke.ai.application.exam.dto.MyPatientListItemResponse;
import com.lzke.ai.application.exam.dto.MyPatientListQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamBatchResultQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamCleanedResultQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamCleanedResultResponse;
import com.lzke.ai.application.exam.dto.PatientExamDepartmentResponse;
import com.lzke.ai.application.exam.dto.PatientExamPatientInfoResponse;
import com.lzke.ai.application.exam.dto.PatientExamPatientQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamResultQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamSessionQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamSessionResponse;
import com.lzke.ai.application.exam.dto.PatientExamSessionSummaryResponse;
import com.lzke.ai.application.exam.dto.PatientExamStatsResponse;
import com.lzke.ai.application.exam.dto.PatientHisItemResultQueryRequest;
import com.lzke.ai.application.exam.dto.PatientHisItemResultResponse;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.security.AesECBEncryptUtils;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;

/**
 * 患者体检结果查询控制器。
 *
 * <p>这组接口面向前端体检报告/指标对比类页面，负责：
 *
 * <ul>
 *     <li>返回可选科室列表</li>
 *     <li>先根据患者信息查询患者基础信息</li>
 *     <li>再分页查询该患者有多少次体检</li>
 *     <li>最后按某次体检和可选科室查询检查结果</li>
 * </ul>
 */
@Tag(name = "患者体检查询", description = "面向 ODC/ODS 体检库的动态查询接口")
@RestController
@RequestMapping("/bs/api/v1/patient-exams")
@RequiredArgsConstructor
public class PatientExamController {

    private final PatientExamApplicationService patientExamApplicationService;

    /**
     * 查询所有可选科室。
     */
    @Operation(summary = "查询体检科室", description = "返回前端多选部门下拉所需的科室编码和名称")
    @GetMapping("/departments")
    public ApiResponse<List<PatientExamDepartmentResponse>> listDepartments() {
        return ApiResponse.ok(patientExamApplicationService.listDepartments());
    }

    /**
     * 查询我的患者列表。
     */
    @Operation(
            summary = "查询我的患者列表",
            description = "根据当前登录用户匹配医疗团队患者，按最近一次体检时间倒序返回患者列表"
    )
    @PostMapping("/my-patients/query")
    public ApiResponse<PageResult<MyPatientListItemResponse>> listMyPatients(
            @Valid @RequestBody MyPatientListQueryRequest request
    ) {
        return ApiResponse.ok(patientExamApplicationService.listMyPatients(request));
    }

    /**
     * 查询我的客户列表。
     */
    @Operation(
            summary = "查询我的客户列表",
            description = "调用已配置的 UI Builder 客户列表接口，并补充每个客户最近一次体检日期"
    )
    @PostMapping("/my-customers/query")
    public ApiResponse<PageResult<MyCustomerListItemResponse>> listMyCustomers(
            @Valid @RequestBody MyCustomerListQueryRequest request
    ) {
        return ApiResponse.ok(patientExamApplicationService.listMyCustomers(request));
    }

    /**
     * 查询体检统计概览。
     */
    @Operation(
            summary = "查询体检统计概览",
            description = "返回最近三年体检客户数、本周体检客户数、上周体检客户数"
    )
    @GetMapping("/stats")
    public ApiResponse<PatientExamStatsResponse> getExamStats() {
        return ApiResponse.ok(patientExamApplicationService.getExamStats());
    }

    /**
     * 查询患者 HIS 单项结果。
     */
    @Operation(
            summary = "查询患者 HIS 单项结果",
            description = "根据身份证号定位 HIS 病历号，合并返回 LIS 检验结果和 PACS 影像结果列表"
    )
    @PostMapping("/his-item-results/query")
    public ApiResponse<List<PatientHisItemResultResponse>> listHisItemResults(
            @Valid @RequestBody PatientHisItemResultQueryRequest request
    ) {
        return ApiResponse.ok(patientExamApplicationService.listHisItemResults(request));
    }
    /**
     * 查询患者基础信息。
     */
    @Operation(
            summary = "查询患者基础信息",
            description = "根据患者筛选条件返回一份患者基础信息，通常取最近一次体检主记录对应的患者信息"
    )
    @PostMapping("/patient-info/query")
    public ApiResponse<PatientExamPatientInfoResponse> getPatientInfo(
            @Valid @RequestBody PatientExamPatientQueryRequest request
    ) {
    	request.setIdCard(AesECBEncryptUtils.decrypt(request.getIdCard()));
    	PatientExamPatientInfoResponse res = patientExamApplicationService.getPatientInfo(request);
    	if (res != null) {
    		res.setIdCard(request.getIdCard());
    	}
        return ApiResponse.ok(res);
    }

    /**
     * 分页查询患者体检记录。
     */
    @Operation(
            summary = "分页查询患者体检记录",
            description = "根据患者筛选条件，分页返回该患者有多少次体检，每次体检附带时间、套餐和结论摘要"
    )
    @PostMapping("/sessions/query")
    public ApiResponse<PageResult<PatientExamSessionSummaryResponse>> listExamSessions(
            @Valid @RequestBody PatientExamSessionQueryRequest request
    ) {
    	request.setIdCard(AesECBEncryptUtils.decrypt(request.getIdCard()));
        return ApiResponse.ok(patientExamApplicationService.listExamSessions(request));
    }

    /**
     * 查询单次体检结果。
     */
    @Operation(
            summary = "查询单次体检结果",
            description = "根据studyId查询某次体检的结果；可选传科室编码列表，不传则查询全部科室"
    )
    @PostMapping("/results/query")
    public ApiResponse<PatientExamSessionResponse> getExamResult(
            @Valid @RequestBody PatientExamResultQueryRequest request
    ) {
        return ApiResponse.ok(patientExamApplicationService.getExamResult(request));
    }

    /**
     * 查询单个体检清洗结果。
     */
    @Operation(
            summary = "查询单个体检清洗结果",
            description = "根据studyId查询体检结果，并通过L1RuleCleaner清洗itemName后返回扁平指标结构"
    )
    @PostMapping("/cleaned-result/query")
    public ApiResponse<PatientExamCleanedResultResponse> getCleanedExamResult(
            @Valid @RequestBody PatientExamCleanedResultQueryRequest request
    ) {
        return ApiResponse.ok(patientExamApplicationService.getCleanedExamResult(request));
    }

    /**
     * 批量查询多次体检结果。
     */
    @Operation(
            summary = "批量查询体检结果",
            description = "根据studyId列表批量查询多次体检结果；可选传科室编码列表，不传则查询全部科室，单次最多支持10份报告"
    )
    @PostMapping("/results/batch-query")
    public ApiResponse<List<PatientExamSessionResponse>> getBatchExamResults(
            @Valid @RequestBody PatientExamBatchResultQueryRequest request
    ) {
    	request.setIdCard(AesECBEncryptUtils.decrypt(request.getIdCard()));
        return ApiResponse.ok(patientExamApplicationService.getBatchExamResults(request));
    }
}
