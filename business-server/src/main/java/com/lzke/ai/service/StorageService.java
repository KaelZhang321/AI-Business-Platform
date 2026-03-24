package com.lzke.ai.service;

import com.lzke.ai.config.MinIOConfig;
import io.minio.*;
import io.minio.http.Method;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
@RequiredArgsConstructor
public class StorageService {

    private final MinioClient minioClient;
    private final MinIOConfig minIOConfig;

    public String upload(MultipartFile file) {
        String originalFilename = file.getOriginalFilename();
        String extension = "";
        if (originalFilename != null && originalFilename.contains(".")) {
            extension = originalFilename.substring(originalFilename.lastIndexOf("."));
        }
        String objectName = UUID.randomUUID() + extension;
        try {
            minioClient.putObject(PutObjectArgs.builder()
                    .bucket(minIOConfig.getBucket())
                    .object(objectName)
                    .stream(file.getInputStream(), file.getSize(), -1)
                    .contentType(file.getContentType())
                    .build());
            log.info("文件上传成功: {}", objectName);
            return objectName;
        } catch (Exception e) {
            throw new RuntimeException("文件上传失败: " + e.getMessage(), e);
        }
    }

    public InputStream download(String objectName) {
        try {
            return minioClient.getObject(GetObjectArgs.builder()
                    .bucket(minIOConfig.getBucket())
                    .object(objectName)
                    .build());
        } catch (Exception e) {
            throw new RuntimeException("文件下载失败: " + e.getMessage(), e);
        }
    }

    public void delete(String objectName) {
        try {
            minioClient.removeObject(RemoveObjectArgs.builder()
                    .bucket(minIOConfig.getBucket())
                    .object(objectName)
                    .build());
            log.info("文件删除成功: {}", objectName);
        } catch (Exception e) {
            throw new RuntimeException("文件删除失败: " + e.getMessage(), e);
        }
    }

    public String getPresignedUrl(String objectName) {
        try {
            return minioClient.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                    .bucket(minIOConfig.getBucket())
                    .object(objectName)
                    .method(Method.GET)
                    .expiry(2, TimeUnit.HOURS)
                    .build());
        } catch (Exception e) {
            throw new RuntimeException("生成预签名URL失败: " + e.getMessage(), e);
        }
    }
}
