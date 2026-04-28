package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.UiApiEndpointRole;
import org.apache.ibatis.annotations.Mapper;

/**
 * UI Builder 接口与角色关系 Mapper。
 */
@Mapper
public interface UiApiEndpointRoleMapper extends BaseMapper<UiApiEndpointRole> {
}
