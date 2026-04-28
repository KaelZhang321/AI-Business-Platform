package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.DoctorCardGroupRelation;
import org.apache.ibatis.annotations.Mapper;

/**
 * 医生工作台分组卡片关系 Mapper。
 */
@Mapper
public interface DoctorCardGroupRelationMapper extends BaseMapper<DoctorCardGroupRelation> {
}
