package com.lzke.ai.controller;

import com.lzke.ai.model.dto.DocumentCreateRequest;
import com.lzke.ai.model.vo.ApiResponse;
import com.lzke.ai.model.vo.DocumentVO;
import com.lzke.ai.model.vo.PageResult;
import com.lzke.ai.service.KnowledgeService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/knowledge")
@RequiredArgsConstructor
public class KnowledgeController {

    private final KnowledgeService knowledgeService;

    @PostMapping("/documents")
    public ApiResponse<DocumentVO> uploadDocument(@Valid @RequestBody DocumentCreateRequest request) {
        return ApiResponse.ok(knowledgeService.createDocument(request));
    }

    @GetMapping("/documents")
    public ApiResponse<PageResult<DocumentVO>> listDocuments(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ApiResponse.ok(knowledgeService.listDocuments(page, size));
    }
}
