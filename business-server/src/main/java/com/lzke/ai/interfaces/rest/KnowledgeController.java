package com.lzke.ai.interfaces.rest;

import com.lzke.ai.annotation.RateLimit;
import com.lzke.ai.application.dto.DocumentCreateRequest;
import com.lzke.ai.application.knowledge.KnowledgeApplicationService;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.DocumentVO;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.service.StorageService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/knowledge")
@RequiredArgsConstructor
public class KnowledgeController {

    private final KnowledgeApplicationService knowledgeApplicationService;
    private final StorageService storageService;

    @PostMapping("/documents")
    public ApiResponse<DocumentVO> uploadDocument(@Valid @RequestBody DocumentCreateRequest request) {
        return ApiResponse.ok(knowledgeApplicationService.createDocument(request));
    }

    @PostMapping("/documents/upload")
    @RateLimit(permits = 20, period = 60)
    public ApiResponse<Map<String, String>> uploadFile(@RequestParam("file") MultipartFile file) {
        String objectName = storageService.upload(file);
        return ApiResponse.ok(Map.of(
                "objectName", objectName,
                "originalName", file.getOriginalFilename() != null ? file.getOriginalFilename() : "",
                "size", String.valueOf(file.getSize())
        ));
    }

    @GetMapping("/documents")
    public ApiResponse<PageResult<DocumentVO>> listDocuments(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ApiResponse.ok(knowledgeApplicationService.listDocuments(page, size));
    }
}
