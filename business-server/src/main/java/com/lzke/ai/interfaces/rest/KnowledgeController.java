package com.lzke.ai.interfaces.rest;

import com.lzke.ai.application.dto.DocumentCreateRequest;
import com.lzke.ai.application.knowledge.KnowledgeApplicationService;
import com.lzke.ai.interfaces.dto.ApiResponse;
import com.lzke.ai.interfaces.dto.DocumentVO;
import com.lzke.ai.interfaces.dto.PageResult;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/knowledge")
@RequiredArgsConstructor
public class KnowledgeController {

    private final KnowledgeApplicationService knowledgeApplicationService;

    @PostMapping("/documents")
    public ApiResponse<DocumentVO> uploadDocument(@Valid @RequestBody DocumentCreateRequest request) {
        return ApiResponse.ok(knowledgeApplicationService.createDocument(request));
    }

    @GetMapping("/documents")
    public ApiResponse<PageResult<DocumentVO>> listDocuments(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ApiResponse.ok(knowledgeApplicationService.listDocuments(page, size));
    }
}
