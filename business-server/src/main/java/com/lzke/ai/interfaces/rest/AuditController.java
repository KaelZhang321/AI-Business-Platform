package com.lzke.ai.interfaces.rest;

import com.lzke.ai.application.audit.AuditApplicationService;
import com.lzke.ai.application.dto.AuditLogQuery;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.AuditLogVO;
import com.lzke.ai.interfaces.dto.PageResult;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/audit")
@RequiredArgsConstructor
public class AuditController {

    private final AuditApplicationService auditApplicationService;

    @GetMapping("/logs")
    public ApiResponse<PageResult<AuditLogVO>> queryLogs(AuditLogQuery query) {
        return ApiResponse.ok(auditApplicationService.queryLogs(query));
    }
}
