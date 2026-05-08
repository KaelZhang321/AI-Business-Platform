package com.lzke.ai.application.workbench.dto;

import com.lzke.ai.application.dto.PageQuery;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * 医生客户定制卡片分页查询条件。
 */
@Data
@EqualsAndHashCode(callSuper = true)
@Schema(description = "医生客户定制卡片分页查询条件")
public class DoctorCustomerCardCustomizeQueryRequest extends PageQuery {

    @Schema(description = "登录员工ID")
    private String employeeId;
    @Schema(description = "客户身份证号")
    private String customerIdCard;
    @Schema(description = "收藏名称，支持模糊查询")
    private String favoriteName;
    @Schema(description = "状态，例如 active / inactive")
    private String status;
}
