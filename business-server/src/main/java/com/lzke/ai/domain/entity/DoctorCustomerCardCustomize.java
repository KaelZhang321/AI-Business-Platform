package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 医生客户定制卡片。
 */
@Data
@TableName("doctor_customer_card_customize")
@Schema(description = "医生客户定制卡片")
public class DoctorCustomerCardCustomize {

    @TableId(type = IdType.ASSIGN_UUID)
    @Schema(description = "主键ID")
    private String id;
    @Schema(description = "登录员工ID")
    private String employeeId;
    @Schema(description = "登录员工名称")
    private String employeeName;
    @Schema(description = "客户身份证号")
    private String customerIdCard;
    @Schema(description = "收藏名称")
    private String favoriteName;
    @Schema(description = "卡片JSON")
    private String cardJson;
    @Schema(description = "状态，例如 active / inactive")
    private String status;
    @Schema(description = "备注")
    private String remark;

    @TableField(fill = FieldFill.INSERT)
    @Schema(description = "创建时间")
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    @Schema(description = "更新时间")
    private OffsetDateTime updatedAt;
}
