package com.lzke.ai.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.lzke.ai.mapper.AuditLogMapper;
import com.lzke.ai.model.dto.AuditLogQuery;
import com.lzke.ai.model.entity.AuditLog;
import com.lzke.ai.model.vo.AuditLogVO;
import com.lzke.ai.model.vo.PageResult;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class AuditService {

    private final AuditLogMapper auditLogMapper;

    public PageResult<AuditLogVO> queryLogs(AuditLogQuery query) {
        Page<AuditLog> pageParam = new Page<>(query.getPage(), query.getSize());
        LambdaQueryWrapper<AuditLog> wrapper = new LambdaQueryWrapper<>();

        if (query.getUserId() != null && !query.getUserId().isEmpty()) {
            wrapper.eq(AuditLog::getUserId, query.getUserId());
        }
        if (query.getIntent() != null && !query.getIntent().isEmpty()) {
            wrapper.eq(AuditLog::getIntent, query.getIntent());
        }
        if (query.getStatus() != null && !query.getStatus().isEmpty()) {
            wrapper.eq(AuditLog::getStatus, query.getStatus());
        }
        wrapper.orderByDesc(AuditLog::getCreatedAt);

        Page<AuditLog> result = auditLogMapper.selectPage(pageParam, wrapper);

        List<AuditLogVO> voList = result.getRecords().stream().map(log -> {
            AuditLogVO vo = new AuditLogVO();
            vo.setId(log.getId());
            vo.setTraceId(log.getTraceId());
            vo.setUserId(log.getUserId());
            vo.setIntent(log.getIntent());
            vo.setModel(log.getModel());
            vo.setInputTokens(log.getInputTokens());
            vo.setOutputTokens(log.getOutputTokens());
            vo.setLatencyMs(log.getLatencyMs());
            vo.setStatus(log.getStatus());
            vo.setCreatedAt(log.getCreatedAt() != null ? log.getCreatedAt().toString() : null);
            return vo;
        }).toList();

        return PageResult.of(voList, result.getTotal(), query.getPage(), query.getSize());
    }
}
