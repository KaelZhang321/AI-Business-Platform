package com.lzke.ai.application.dto;

import jakarta.validation.constraints.AssertTrue;
import lombok.Data;
import lombok.EqualsAndHashCode;
import org.springframework.format.annotation.DateTimeFormat;

import java.time.LocalDate;

/**
 * 待办聚合查询参数
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class TaskAggregateQuery extends PageQuery {

    private String userId;
    private String status;
    private String sourceSystem;
    private String priority;

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
