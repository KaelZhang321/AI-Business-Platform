package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * 功能医学 AI 推荐方案映射明细。
 *
 * <p>该表按 Excel 明细一行一条记录存储，便于后续直接做筛选、检索和人工维护。
 */
@Data
@TableName("function_medicine_ai_mapping")
public class FunctionMedicineAiMapping {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /**
     * Excel 序号列。
     */
    private Integer serialNo;

    /**
     * 所属系统。
     */
    private String systemName;

    /**
     * 项目名称。
     */
    private String projectName;

    /**
     * 指标代码。
     */
    private String indicatorCode;

    /**
     * 指标名称。
     */
    private String indicatorName;

    /**
     * 所属检查项目名称。
     */
    private String examProjectName;

    /**
     * 理想值范围。
     */
    private String idealRange;

    /**
     * 套餐/版本。
     */
    private String packageVersion;

    /**
     * 价格原始文本。
     */
    private String priceText;

    /**
     * 核心功效。
     */
    private String coreEffect;

    /**
     * 适应症。
     */
    private String indications;

    /**
     * 禁忌症/风险。
     */
    private String contraindications;

    /**
     * 备注。
     */
    private String remark;

    /**
     * 数据状态：active / inactive。
     */
    private String status;

    /**
     * 来源 sheet 名称。
     */
    private String sourceSheetName;

    /**
     * 来源 Excel 行号。
     */
    private Integer sourceRowNo;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
