package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 语义字段别名实体。
 *
 * <p>该表把某个接口中的原始字段名映射到标准语义字段，
 * 用于解决不同接口命名不一致的问题，例如：
 *
 * <ul>
 *     <li>`sex` -> `gender`</li>
 *     <li>`userSex` -> `gender`</li>
 * </ul>
 */
@Data
@TableName("semantic_field_alias")
public class SemanticFieldAlias {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String standardKey;
    private String alias;
    private String apiId;
    private String source;
    private LocalDateTime createdAt;
}
