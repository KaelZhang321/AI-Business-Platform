//package com.lzke.ai.config;
//
//import org.flowable.spring.SpringProcessEngineConfiguration;
//import org.flowable.spring.boot.EngineConfigurationConfigurer;
//import org.springframework.beans.factory.annotation.Value;
//import org.springframework.boot.autoconfigure.jdbc.DataSourceProperties;
//import org.springframework.context.annotation.Bean;
//import org.springframework.context.annotation.Configuration;
//import org.springframework.context.annotation.Primary;
//import org.springframework.util.StringUtils;
//import org.springframework.transaction.PlatformTransactionManager;
//
//import javax.sql.DataSource;
//
//@Configuration
//public class FlowableConfig {
//
//    @Value("${flowable.database-type:}")
//    private String flowableDatabaseType;
//
//    @Bean
//    @Primary
//    public DataSource primaryDataSource(DataSourceProperties properties) {
//        return properties.initializeDataSourceBuilder().build();
//    }
//
//    @Bean
//    public EngineConfigurationConfigurer<SpringProcessEngineConfiguration> flowableDataSourceConfigurer(
//            DataSource primaryDataSource,
//            PlatformTransactionManager transactionManager) {
//        return engineConfiguration -> {
//            engineConfiguration.setDataSource(primaryDataSource);
//            engineConfiguration.setTransactionManager(transactionManager);
//            if (StringUtils.hasText(flowableDatabaseType)) {
//                engineConfiguration.setDatabaseType(flowableDatabaseType);
//            }
//        };
//    }
//}
