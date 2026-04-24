package com.lzke.ai.service;

import com.lzke.ai.config.MinIOConfig;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import io.minio.*;
import io.minio.http.Method;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.InputStream;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
@RequiredArgsConstructor
public class StorageService {

    private static final Set<String> ALLOWED_EXTENSIONS = Set.of(
            ".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xlsx", ".xls", ".pptx", ".png", ".jpg", ".jpeg");
    private static final long MAX_FILE_SIZE = 100 * 1024 * 1024L; // 100MB

    private final MinioClient minioClient;
    private final MinIOConfig minIOConfig;

    public String upload(MultipartFile file) {
        // 文件大小校验
        if (file.getSize() > MAX_FILE_SIZE) {
            throw new BusinessException(ErrorCode.STORAGE_ERROR, "文件大小不能超过 100MB");
        }

        String originalFilename = file.getOriginalFilename();
        String extension = "";
        if (originalFilename != null && originalFilename.contains(".")) {
            extension = originalFilename.substring(originalFilename.lastIndexOf(".")).toLowerCase();
        }

        // 文件类型白名单校验
        if (!extension.isEmpty() && !ALLOWED_EXTENSIONS.contains(extension)) {
            throw new BusinessException(ErrorCode.STORAGE_ERROR,
                    "不支持的文件类型: " + extension + "，允许: " + ALLOWED_EXTENSIONS);
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
            throw new BusinessException(ErrorCode.STORAGE_ERROR, "文件上传失败: " + e.getMessage(), e);
        }
    }

    public InputStream download(String objectName) {
        try {
            return minioClient.getObject(GetObjectArgs.builder()
                    .bucket(minIOConfig.getBucket())
                    .object(objectName)
                    .build());
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.STORAGE_ERROR, "文件下载失败: " + e.getMessage(), e);
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
            throw new BusinessException(ErrorCode.STORAGE_ERROR, "文件删除失败: " + e.getMessage(), e);
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
            throw new BusinessException(ErrorCode.STORAGE_ERROR, "生成预签名URL失败: " + e.getMessage(), e);
        }
    }
}
