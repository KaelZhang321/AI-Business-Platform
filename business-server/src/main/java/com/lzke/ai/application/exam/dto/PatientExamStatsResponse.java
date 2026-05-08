package com.lzke.ai.application.exam.dto;

import lombok.Data;

/**
 * 体检客户统计概览。
 */
@Data
public class PatientExamStatsResponse {

    /**
     * 最近三年有体检记录的客户数量。
     */
    private long recentThreeYearsPatientCount;

    /**
     * 本周体检客户数量。
     */
    private long thisWeekPatientCount;

    /**
     * 上周体检客户数量。
     */
    private long lastWeekPatientCount;
}
