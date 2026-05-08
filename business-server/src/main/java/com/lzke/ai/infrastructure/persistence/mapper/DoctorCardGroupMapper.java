package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.DoctorCardGroup;
import org.apache.ibatis.annotations.Mapper;

/**
 * 医生工作台卡片分组 Mapper。
 */
@Mapper
public interface DoctorCardGroupMapper extends BaseMapper<DoctorCardGroup> {
}
