package com.lzke.ai.controller;

import com.lzke.ai.service.KnowledgeService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/knowledge")
@RequiredArgsConstructor
public class KnowledgeController {

    private final KnowledgeService knowledgeService;

    @PostMapping("/documents")
    public ResponseEntity<Map<String, Object>> uploadDocument(@RequestBody Map<String, Object> request) {
        return ResponseEntity.ok(knowledgeService.createDocument(request));
    }

    @GetMapping("/documents")
    public ResponseEntity<?> listDocuments(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(knowledgeService.listDocuments(page, size));
    }
}
