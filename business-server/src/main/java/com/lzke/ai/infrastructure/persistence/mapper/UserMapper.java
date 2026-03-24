package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.lzke.ai.domain.entity.User;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.Optional;
import java.util.UUID;

@Mapper
public interface UserMapper extends BaseMapper<User> {

    @Select("SELECT * FROM users WHERE username = #{username} LIMIT 1")
    Optional<User> findByUsername(String username);

    @Select("SELECT * FROM users WHERE id = #{id} LIMIT 1")
    Optional<User> findById(UUID id);
}
