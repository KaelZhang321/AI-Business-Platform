package com.lzke.ai.interfaces.rest;

import com.lzke.ai.annotation.RateLimit;
import com.lzke.ai.application.dto.DocumentCreateRequest;
import com.lzke.ai.application.knowledge.KnowledgeApplicationService;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.DocumentVO;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.service.StorageService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@Tag(name = "知识库", description = "文档管理与文件上传")
@RestController
@RequestMapping("/api/v1/knowledge")
@RequiredArgsConstructor
public class KnowledgeController {

    private final KnowledgeApplicationService knowledgeApplicationService;
    private final StorageService storageService;

    @Operation(summary = "创建文档", description = "创建知识库文档并触发异步处理")
    @PostMapping("/documents")
    public ApiResponse<DocumentVO> uploadDocument(@Valid @RequestBody DocumentCreateRequest request) {
        return ApiResponse.ok(knowledgeApplicationService.createDocument(request));
    }

    @Operation(summary = "上传文件", description = "上传文件到 MinIO 对象存储")
    @PostMapping("/documents/upload")
    @RateLimit(permits = 20, period = 60)
    public ApiResponse<Map<String, String>> uploadFile(@Parameter(description = "待上传文件") @RequestParam("file") MultipartFile file) {
        String objectName = storageService.upload(file);
        return ApiResponse.ok(Map.of(
                "objectName", objectName,
                "originalName", file.getOriginalFilename() != null ? file.getOriginalFilename() : "",
                "size", String.valueOf(file.getSize())
        ));
    }

    @Operation(summary = "文档列表", description = "分页查询知识库文档")
    @GetMapping("/documents")
    public ApiResponse<PageResult<DocumentVO>> listDocuments(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ApiResponse.ok(knowledgeApplicationService.listDocuments(page, size));
    }
}
