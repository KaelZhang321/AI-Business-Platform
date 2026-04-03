package com.lzke.ai.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.OffsetDateTime;

/**
 * UI Builder 页面节点实体。
 *
 * <p>对应 `ui_page_nodes`，用树形结构描述页面中的组件节点。
 */
@Data
@TableName("ui_page_nodes")
public class UiPageNode {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String pageId;
    private String parentId;
    private String nodeKey;
    private String nodeType;
    private String nodeName;
    private Integer sortOrder;
    private String slotName;
    private String propsConfig;
    private String styleConfig;
    private String status;

    @TableField(fill = FieldFill.INSERT)
    private OffsetDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private OffsetDateTime updatedAt;
}
