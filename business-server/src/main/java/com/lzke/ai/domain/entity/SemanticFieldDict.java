package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 语义字段字典主表实体。
 *
 * <p>该表定义系统内的标准字段语义，包括：
 *
 * <ul>
 *     <li>标准字段 key</li>
 *     <li>展示名称</li>
 *     <li>组件类型</li>
 *     <li>全局值映射</li>
 * </ul>
 *
 * <p>这些信息后续既可以给 AI 做上下文，也可以给字段编排页面做标准字段候选来源。
 */
@Data
@TableName("semantic_field_dict")
public class SemanticFieldDict {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String standardKey;
    private String label;
    private String fieldType;
    private String category;
    private String valueMap;
    private String description;
    private Integer isActive;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
