package com.lzke.ai.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import javax.sql.DataSource;

@Getter
@Setter
@Configuration
@ConfigurationProperties(prefix = "app.clickhouse")
public class ClickHouseConfig {

    private String url = "jdbc:clickhouse://localhost:8123/ai_platform_logs";
    private String username = "default";
    private String password = "";

    @Bean(name = "clickHouseDataSource")
    public DataSource clickHouseDataSource() {
        DriverManagerDataSource ds = new DriverManagerDataSource();
        ds.setDriverClassName("com.clickhouse.jdbc.ClickHouseDriver");
        ds.setUrl(url);
        ds.setUsername(username);
        ds.setPassword(password);
        return ds;
    }

    @Bean(name = "clickHouseJdbcTemplate")
    public JdbcTemplate clickHouseJdbcTemplate() {
        return new JdbcTemplate(clickHouseDataSource());
    }
}
