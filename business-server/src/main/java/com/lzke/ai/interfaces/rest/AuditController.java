package com.lzke.ai.interfaces.rest;

import com.lzke.ai.annotation.RateLimit;
import com.lzke.ai.application.audit.AuditApplicationService;
import com.lzke.ai.application.dto.AuditLogQuery;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.AuditLogVO;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.service.AnalyticsService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Tag(name = "审计日志", description = "审计日志查询与 ClickHouse 分析")
@RestController
@RequestMapping("/api/v1/audit")
@RequiredArgsConstructor
public class AuditController {

    private final AuditApplicationService auditApplicationService;
    private final AnalyticsService analyticsService;

    @Operation(summary = "查询审计日志", description = "分页查询审计日志，支持多条件过滤")
    @GetMapping("/logs")
    public ApiResponse<PageResult<AuditLogVO>> queryLogs(AuditLogQuery query) {
        return ApiResponse.ok(auditApplicationService.queryLogs(query));
    }

    @Operation(summary = "按意图统计", description = "ClickHouse 聚合：按意图类型统计请求量")
    @GetMapping("/analytics/by-intent")
    @RateLimit(permits = 60, period = 60)
    public ApiResponse<List<Map<String, Object>>> analyticsByIntent(
            @Parameter(description = "起始日期 yyyy-MM-dd") @RequestParam String startDate,
            @Parameter(description = "结束日期 yyyy-MM-dd") @RequestParam String endDate) {
        return ApiResponse.ok(analyticsService.statsByIntent(startDate, endDate));
    }

    @Operation(summary = "按模型统计", description = "ClickHouse 聚合：按模型统计请求量")
    @GetMapping("/analytics/by-model")
    public ApiResponse<List<Map<String, Object>>> analyticsByModel(
            @Parameter(description = "起始日期 yyyy-MM-dd") @RequestParam String startDate,
            @Parameter(description = "结束日期 yyyy-MM-dd") @RequestParam String endDate) {
        return ApiResponse.ok(analyticsService.statsByModel(startDate, endDate));
    }

    @Operation(summary = "按小时统计", description = "ClickHouse 聚合：按小时统计请求量")
    @GetMapping("/analytics/by-hour")
    public ApiResponse<List<Map<String, Object>>> analyticsByHour(
            @Parameter(description = "日期 yyyy-MM-dd") @RequestParam String date) {
        return ApiResponse.ok(analyticsService.statsByHour(date));
    }
}
