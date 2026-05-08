package com.lzke.ai.application.recommend;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.lzke.ai.application.dto.FunctionMedicineAiMappingQueryRequest;
import com.lzke.ai.application.dto.FunctionMedicineAiMappingRequest;
import com.lzke.ai.domain.entity.FunctionMedicineAiMapping;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import com.lzke.ai.infrastructure.persistence.mapper.FunctionMedicineAiMappingMapper;
import com.lzke.ai.interfaces.dto.PageResult;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

/**
 * 功能医学 AI 推荐方案映射应用服务。
 */
@Service
@RequiredArgsConstructor
public class FunctionMedicineAiMappingApplicationService {

    private final FunctionMedicineAiMappingMapper functionMedicineAiMappingMapper;

    /**
     * 分页查询映射明细。
     */
    public PageResult<FunctionMedicineAiMapping> listMappings(FunctionMedicineAiMappingQueryRequest request) {
        FunctionMedicineAiMappingQueryRequest query = request == null ? new FunctionMedicineAiMappingQueryRequest() : request;
        Page<FunctionMedicineAiMapping> page = new Page<>(query.getPage(), query.getSize());
        LambdaQueryWrapper<FunctionMedicineAiMapping> wrapper = new LambdaQueryWrapper<>();
        wrapper.like(StringUtils.hasText(query.getSystemName()), FunctionMedicineAiMapping::getSystemName, query.getSystemName())
                .like(StringUtils.hasText(query.getProjectName()), FunctionMedicineAiMapping::getProjectName, query.getProjectName())
                .like(StringUtils.hasText(query.getPackageVersion()), FunctionMedicineAiMapping::getPackageVersion, query.getPackageVersion())
                .like(StringUtils.hasText(query.getIndicatorCode()), FunctionMedicineAiMapping::getIndicatorCode, query.getIndicatorCode())
                .like(StringUtils.hasText(query.getIndicatorName()), FunctionMedicineAiMapping::getIndicatorName, query.getIndicatorName())
                .eq(StringUtils.hasText(query.getStatus()), FunctionMedicineAiMapping::getStatus, query.getStatus())
                .orderByAsc(FunctionMedicineAiMapping::getSerialNo)
                .orderByAsc(FunctionMedicineAiMapping::getSourceRowNo)
                .orderByDesc(FunctionMedicineAiMapping::getUpdatedAt);
        Page<FunctionMedicineAiMapping> result = functionMedicineAiMappingMapper.selectPage(page, wrapper);
        return PageResult.of(result.getRecords(), result.getTotal(), (int) result.getCurrent(), (int) result.getSize());
    }

    /**
     * 查询单条详情。
     */
    public FunctionMedicineAiMapping getMapping(String mappingId) {
        FunctionMedicineAiMapping mapping = functionMedicineAiMappingMapper.selectById(mappingId);
        if (mapping == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到功能医学 AI 推荐方案映射: " + mappingId);
        }
        return mapping;
    }

    /**
     * 新增映射。
     */
    @Transactional
    public FunctionMedicineAiMapping createMapping(FunctionMedicineAiMappingRequest request) {
        FunctionMedicineAiMapping entity = new FunctionMedicineAiMapping();
        copyRequest(entity, request);
        functionMedicineAiMappingMapper.insert(entity);
        return entity;
    }

    /**
     * 更新映射。
     */
    @Transactional
    public FunctionMedicineAiMapping updateMapping(String mappingId, FunctionMedicineAiMappingRequest request) {
        FunctionMedicineAiMapping entity = getMapping(mappingId);
        copyRequest(entity, request);
        functionMedicineAiMappingMapper.updateById(entity);
        return getMapping(mappingId);
    }

    /**
     * 删除映射。
     */
    @Transactional
    public void deleteMapping(String mappingId) {
        if (functionMedicineAiMappingMapper.deleteById(mappingId) <= 0) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到功能医学 AI 推荐方案映射: " + mappingId);
        }
    }

    private void copyRequest(FunctionMedicineAiMapping entity, FunctionMedicineAiMappingRequest request) {
        entity.setSerialNo(request.getSerialNo());
        entity.setSystemName(trimToNull(request.getSystemName()));
        entity.setProjectName(trimToNull(request.getProjectName()));
        entity.setIndicatorCode(normalizeDash(request.getIndicatorCode()));
        entity.setIndicatorName(normalizeDash(request.getIndicatorName()));
        entity.setExamProjectName(normalizeDash(request.getExamProjectName()));
        entity.setIdealRange(normalizeDash(request.getIdealRange()));
        entity.setPackageVersion(trimToNull(request.getPackageVersion()));
        entity.setPriceText(trimToNull(request.getPriceText()));
        entity.setCoreEffect(trimToNull(request.getCoreEffect()));
        entity.setIndications(trimToNull(request.getIndications()));
        entity.setContraindications(trimToNull(request.getContraindications()));
        entity.setRemark(trimToNull(request.getRemark()));
        entity.setStatus(StringUtils.hasText(request.getStatus()) ? request.getStatus().trim() : "active");
        entity.setSourceSheetName(StringUtils.hasText(request.getSourceSheetName()) ? request.getSourceSheetName().trim() : "产品映射库");
        entity.setSourceRowNo(request.getSourceRowNo());
    }

    private String trimToNull(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        return value.trim();
    }

    private String normalizeDash(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        String trimmed = value.trim();
        return "-".equals(trimmed) ? null : trimmed;
    }
}
