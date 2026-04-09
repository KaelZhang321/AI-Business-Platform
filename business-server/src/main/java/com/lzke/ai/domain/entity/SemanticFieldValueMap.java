package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

/**
 * 语义字段值映射扩展实体。
 *
 * <p>该表用于表达“接口原始值 -> 标准值”的转换规则，
 * 同时支持：
 *
 * <ul>
 *     <li>全局映射（apiId 为空）</li>
 *     <li>接口级覆盖（apiId 有值）</li>
 * </ul>
 */
@Data
@TableName("semantic_field_value_map")
public class SemanticFieldValueMap {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String standardKey;
    private String apiId;
    private String standardValue;
    private String rawValue;
    private Integer sortOrder;
}
