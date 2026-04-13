package com.lzke.ai.application.rule.service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import javax.sql.DataSource;

import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import com.baomidou.dynamic.datasource.DynamicRoutingDataSource;
import com.lzke.ai.application.rule.dto.RuleDataSourceResponse;

/**
 * 规则引擎 JdbcTemplate 解析器。
 *
 * <p>职责：
 * <ul>
 *     <li>为 SQL 节点按数据源 key 动态解析 {@link JdbcTemplate}</li>
 *     <li>返回规则引擎可选的数据源列表，供前端节点编排下拉选择</li>
 *     <li>在节点未显式指定数据源时，回退到系统默认数据源</li>
 * </ul>
 */
@Component
public class RuleJdbcTemplateResolver {

    private final DataSource dataSource;
    private final String configuredDefaultDataSourceKey;
    private final Map<String, JdbcTemplate> jdbcTemplateCache = new ConcurrentHashMap<>();

    public RuleJdbcTemplateResolver(
            DataSource dataSource,
            @Value("${app.rule.default-sql-datasource:}") String configuredDefaultDataSourceKey
    ) {
        this.dataSource = dataSource;
        this.configuredDefaultDataSourceKey = configuredDefaultDataSourceKey;
    }

    /**
     * 获取前端可选的数据源列表。
     */
    public List<RuleDataSourceResponse> listDataSources() {
        if (!(dataSource instanceof DynamicRoutingDataSource dynamicRoutingDataSource)) {
            return List.of(new RuleDataSourceResponse("default", "default", true));
        }

        Map<String, DataSource> dataSourceMap = dynamicRoutingDataSource.getDataSources();
        String defaultKey = resolveDefaultDataSourceKey(dynamicRoutingDataSource);

        List<RuleDataSourceResponse> result = new ArrayList<>();
        dataSourceMap.keySet().stream()
                .filter(StringUtils::isNotBlank)
                .sorted(Comparator.naturalOrder())
                .forEach(key -> result.add(new RuleDataSourceResponse(key, key, key.equals(defaultKey))));
        return result;
    }

    /**
     * 根据节点配置的数据源 key 解析 JdbcTemplate。
     *
     * <p>未配置时会自动回退到默认数据源。
     */
    public JdbcTemplate resolve(String requestedDataSourceKey) {
        if (!(dataSource instanceof DynamicRoutingDataSource dynamicRoutingDataSource)) {
            return jdbcTemplateCache.computeIfAbsent("default", key -> new JdbcTemplate(dataSource));
        }

        String effectiveKey = resolveEffectiveKey(dynamicRoutingDataSource, requestedDataSourceKey);
        DataSource resolvedDataSource = dynamicRoutingDataSource.getDataSource(effectiveKey);
        if (resolvedDataSource == null) {
            throw new IllegalStateException("Datasource '" + effectiveKey + "' is not configured");
        }
        return jdbcTemplateCache.computeIfAbsent(effectiveKey, key -> new JdbcTemplate(resolvedDataSource));
    }

    private String resolveEffectiveKey(DynamicRoutingDataSource dynamicRoutingDataSource, String requestedDataSourceKey) {
        String normalizedRequestedKey = StringUtils.trimToNull(requestedDataSourceKey);
        if (normalizedRequestedKey != null) {
            DataSource explicitDataSource = dynamicRoutingDataSource.getDataSource(normalizedRequestedKey);
            if (explicitDataSource == null) {
                throw new IllegalStateException("Datasource '" + normalizedRequestedKey + "' is not configured");
            }
            return normalizedRequestedKey;
        }
        return resolveDefaultDataSourceKey(dynamicRoutingDataSource);
    }

    private String resolveDefaultDataSourceKey(DynamicRoutingDataSource dynamicRoutingDataSource) {
        String normalizedConfiguredKey = StringUtils.trimToNull(configuredDefaultDataSourceKey);
        if (normalizedConfiguredKey != null && dynamicRoutingDataSource.getDataSource(normalizedConfiguredKey) != null) {
            return normalizedConfiguredKey;
        }
        if (dynamicRoutingDataSource.getDataSource("odc") != null) {
            return "odc";
        }
        return dynamicRoutingDataSource.getDataSources().keySet().stream()
                .filter(StringUtils::isNotBlank)
                .sorted()
                .findFirst()
                .orElseThrow(() -> new IllegalStateException("No datasource configured for rule engine"));
    }
}
