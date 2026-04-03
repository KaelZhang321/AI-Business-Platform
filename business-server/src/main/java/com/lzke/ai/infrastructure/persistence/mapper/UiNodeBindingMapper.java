package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.UiNodeBinding;
import org.apache.ibatis.annotations.Mapper;

/**
 * UI Builder 节点字段绑定 Mapper。
 */
@Mapper
public interface UiNodeBindingMapper extends BaseMapper<UiNodeBinding> {
}
