package com.lzke.ai.config;

import javax.sql.DataSource;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Configuration
@ConditionalOnProperty(prefix = "app.clickhouse", name = "enabled", havingValue = "true", matchIfMissing = true)
@ConfigurationProperties(prefix = "app.clickhouse")
public class ClickHouseConfig {

	@Value("${app.clickhouse.url:jdbc:clickhouse://localhost:8123/ai_platform_logs}")
    private String url;
	@Value("${app.clickhouse.username:default}")
    private String username;
	@Value("${app.clickhouse.password:}")
    private String password;

    @Bean(name = "clickHouseDataSource")
    public DataSource clickHouseDataSource() {
        HikariConfig config = new HikariConfig();
        String urlWithOptions = url.contains("?") ? url + "&compress=0" : url + "?compress=0";
        config.setJdbcUrl(urlWithOptions);
        config.setUsername(username);
        config.setPassword(password);
        config.setDriverClassName("com.clickhouse.jdbc.ClickHouseDriver");
        config.setMaximumPoolSize(5);
        config.setMinimumIdle(1);
        config.setConnectionTimeout(10000);
        config.setIdleTimeout(300000);
        config.setMaxLifetime(1800000);
        config.setPoolName("ai-platform-clickhouse");
        return new HikariDataSource(config);
    }

    @Bean(name = "clickHouseJdbcTemplate")
    public JdbcTemplate clickHouseJdbcTemplate() {
        return new JdbcTemplate(clickHouseDataSource());
    }
}
