package com.lzke.ai.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import io.minio.BucketExistsArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import lombok.Getter;
import lombok.Setter;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Getter
@Setter
@Configuration
@ConfigurationProperties(prefix = "app.minio")
public class MinIOConfig {

	@Value("${app.minio.endpoint:http://localhost:9000}")
    private String endpoint;
	@Value("${app.minio.access-key:minioadmin}")
    private String accessKey;
	@Value("${app.minio.secret-key:minioadmin_dev}")
    private String secretKey;
	@Value("${app.minio.bucket:ai-platform-docs}")
    private String bucket;

    @Bean
    public MinioClient minioClient() {
        MinioClient client = MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
        try {
            boolean exists = client.bucketExists(BucketExistsArgs.builder().bucket(bucket).build());
            if (!exists) {
                client.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
                log.info("MinIO bucket '{}' 创建成功", bucket);
            }
        } catch (Exception e) {
            log.warn("MinIO 初始化检查失败: {}", e.getMessage());
        }
        return client;
    }
}
