package com.lzke.ai.application.dto;

import jakarta.validation.constraints.AssertTrue;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.springframework.format.annotation.DateTimeFormat;

import java.time.LocalDate;

/**
 * 审计日志查询参数
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class AuditLogQuery extends PageQuery {

    private String userId;
    private String intent;
    private String status;

    @DateTimeFormat(pattern = "yyyy-MM-dd")
    private LocalDate startDate;

    @DateTimeFormat(pattern = "yyyy-MM-dd")
    private LocalDate endDate;

    @AssertTrue(message = "结束日期不能早于开始日期")
    private boolean isValidDateRange() {
        if (startDate == null || endDate == null) return true;
        return !endDate.isBefore(startDate);
    }
}
