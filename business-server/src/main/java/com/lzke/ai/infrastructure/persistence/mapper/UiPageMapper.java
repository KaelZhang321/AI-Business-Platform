package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.UiPage;
import org.apache.ibatis.annotations.Mapper;

/**
 * UI Builder 页面 Mapper。
 */
@Mapper
public interface UiPageMapper extends BaseMapper<UiPage> {
}
