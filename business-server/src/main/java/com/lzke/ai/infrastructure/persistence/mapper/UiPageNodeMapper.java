package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.UiPageNode;
import org.apache.ibatis.annotations.Mapper;

/**
 * UI Builder 页面节点 Mapper。
 */
@Mapper
public interface UiPageNodeMapper extends BaseMapper<UiPageNode> {
}
