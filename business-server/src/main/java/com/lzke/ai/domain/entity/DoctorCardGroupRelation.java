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
 * 医生工作台分组卡片关系。
 */
@Data
@TableName("doctor_card_group_relation")
@Schema(description = "医生工作台分组卡片关系")
public class DoctorCardGroupRelation {

    @TableId(type = IdType.ASSIGN_UUID)
    @Schema(description = "主键ID")
    private String id;
    @Schema(description = "分组ID")
    private String groupId;
    @Schema(description = "卡片配置ID")
    private String cardConfigId;
    @Schema(description = "卡片排序")
    private Integer cardSort;
    @Schema(description = "是否展示：1展示，0隐藏")
    private Integer visibleFlag;
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
