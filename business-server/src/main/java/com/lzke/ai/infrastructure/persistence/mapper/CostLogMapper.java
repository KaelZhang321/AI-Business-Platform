package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.CostLog;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface CostLogMapper extends BaseMapper<CostLog> {
}
