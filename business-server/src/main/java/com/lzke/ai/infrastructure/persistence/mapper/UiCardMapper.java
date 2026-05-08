package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.UiCard;
import org.apache.ibatis.annotations.Mapper;

/**
 * UI Builder 卡片 Mapper。
 */
@Mapper
public interface UiCardMapper extends BaseMapper<UiCard> {
}
