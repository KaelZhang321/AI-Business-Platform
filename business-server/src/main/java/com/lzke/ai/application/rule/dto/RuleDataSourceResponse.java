package com.lzke.ai.application.rule.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 规则引擎可选数据源返回对象。
 *
 * <p>前端在配置 SQL 节点时使用该列表作为下拉选项，避免手输数据源 key。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class RuleDataSourceResponse {

    /**
     * 数据源唯一 key。
     */
    private String key;

    /**
     * 页面展示名称。
     */
    private String label;

    /**
     * 是否为默认数据源。
     */
    private boolean defaultSelected;
}
