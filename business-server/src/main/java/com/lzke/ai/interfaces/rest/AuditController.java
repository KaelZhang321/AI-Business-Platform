package com.lzke.ai.interfaces.rest;

import com.lzke.ai.annotation.RateLimit;
import com.lzke.ai.application.audit.AuditApplicationService;
import com.lzke.ai.application.dto.AuditLogQuery;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.AuditLogVO;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.service.AnalyticsService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/audit")
@RequiredArgsConstructor
public class AuditController {

    private final AuditApplicationService auditApplicationService;
    private final AnalyticsService analyticsService;

    @GetMapping("/logs")
    public ApiResponse<PageResult<AuditLogVO>> queryLogs(AuditLogQuery query) {
        return ApiResponse.ok(auditApplicationService.queryLogs(query));
    }

    @GetMapping("/analytics/by-intent")
    @RateLimit(permits = 60, period = 60)
    public ApiResponse<List<Map<String, Object>>> analyticsByIntent(
            @RequestParam String startDate, @RequestParam String endDate) {
        return ApiResponse.ok(analyticsService.statsByIntent(startDate, endDate));
    }

    @GetMapping("/analytics/by-model")
    public ApiResponse<List<Map<String, Object>>> analyticsByModel(
            @RequestParam String startDate, @RequestParam String endDate) {
        return ApiResponse.ok(analyticsService.statsByModel(startDate, endDate));
    }

    @GetMapping("/analytics/by-hour")
    public ApiResponse<List<Map<String, Object>>> analyticsByHour(@RequestParam String date) {
        return ApiResponse.ok(analyticsService.statsByHour(date));
    }
}
