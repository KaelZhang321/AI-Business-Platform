package com.lzke.ai.application.exam.dto;

import com.lzke.ai.interfaces.dto.PageResult;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 患者体检查询聚合响应。
 *
 * <p>接口不再直接返回平铺的明细行，而是拆成两层：
 *
 * <ul>
 *     <li>顶层返回患者基础信息，供前端页头或患者卡片展示</li>
 *     <li>分页返回每次体检记录，每次体检下再按科室聚合细项结果</li>
 * </ul>
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PatientExamQueryResponse {

    /**
     * 患者基础信息。
     */
    private PatientExamPatientInfoResponse patientInfo;

    /**
     * 按体检主记录分页后的结果。
     */
    private PageResult<PatientExamSessionResponse> exams;
}
