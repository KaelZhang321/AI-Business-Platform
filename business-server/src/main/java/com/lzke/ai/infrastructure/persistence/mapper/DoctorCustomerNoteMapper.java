package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.DoctorCustomerNote;
import org.apache.ibatis.annotations.Mapper;

/**
 * 医生客户便签 Mapper。
 */
@Mapper
public interface DoctorCustomerNoteMapper extends BaseMapper<DoctorCustomerNote> {
}
