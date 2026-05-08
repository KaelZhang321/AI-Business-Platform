package com.lzke.ai.application.exam.dto;

import com.lzke.ai.application.dto.PageQuery;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 我的患者列表查询条件。
 *
 * <p>列表面向当前登录员工，只返回该员工医疗团队下的患者信息。
 */
@Data
@EqualsAndHashCode(callSuper = true)
public class MyPatientListQueryRequest extends PageQuery {

    /**
     * 患者姓名，模糊查询。
     */
    private String patientName;

    /**
     * 身份证号，模糊查询。
     */
    private String idCard;

    /**
     * 手机号，模糊查询。
     */
    private String mobile;
}
