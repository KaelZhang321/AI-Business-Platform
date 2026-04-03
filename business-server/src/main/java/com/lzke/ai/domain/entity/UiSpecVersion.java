package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 发布版本实体。
 *
 * <p>对应 `ui_spec_versions`，保存每次发布时冻结下来的最终 spec 内容。
 */
@Data
@TableName("ui_spec_versions")
public class UiSpecVersion {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String projectId;
    private String pageId;
    private Integer versionNo;
    private String publishStatus;
    private String specContent;
    private String sourceSnapshot;
    private String publishedBy;
    private OffsetDateTime publishedAt;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;
}
