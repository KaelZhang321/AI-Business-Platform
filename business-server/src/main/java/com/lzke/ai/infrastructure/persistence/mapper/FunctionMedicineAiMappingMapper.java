package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.FunctionMedicineAiMapping;
import org.apache.ibatis.annotations.Mapper;

/**
 * 功能医学 AI 推荐方案映射 Mapper。
 */
@Mapper
public interface FunctionMedicineAiMappingMapper extends BaseMapper<FunctionMedicineAiMapping> {
}
