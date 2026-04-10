package com.lzke.ai.application.rule.config;

import javax.sql.DataSource;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

import com.baomidou.dynamic.datasource.DynamicRoutingDataSource;

/**
 * Provide a JdbcTemplate bean for ODC access.
 */
@Configuration
public class OdcJdbcTemplateConfig {

	@Bean(name = "odcJdbcTemplate")
	public JdbcTemplate odcJdbcTemplate(DataSource dataSource) {
		if (!(dataSource instanceof DynamicRoutingDataSource dynamicRoutingDataSource)) {
			throw new IllegalStateException("Current dataSource is not DynamicRoutingDataSource");
		}
		DataSource odcDataSource = dynamicRoutingDataSource.getDataSource("odc");
		if (odcDataSource == null) {
			throw new IllegalStateException("Datasource 'odc' is not configured");
		}
		return new JdbcTemplate(odcDataSource);
	}
}