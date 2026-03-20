package com.lzke.ai.controller;

import com.lzke.ai.model.dto.AuditLogQuery;
import com.lzke.ai.model.vo.ApiResponse;
import com.lzke.ai.model.vo.AuditLogVO;
import com.lzke.ai.model.vo.PageResult;
import com.lzke.ai.service.AuditService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/audit")
@RequiredArgsConstructor
public class AuditController {

    private final AuditService auditService;

    @GetMapping("/logs")
    public ApiResponse<PageResult<AuditLogVO>> queryLogs(AuditLogQuery query) {
        return ApiResponse.ok(auditService.queryLogs(query));
    }
}
