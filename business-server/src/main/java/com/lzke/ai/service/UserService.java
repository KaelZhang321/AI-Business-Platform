package com.lzke.ai.service;

import com.lzke.ai.infrastructure.persistence.mapper.UserMapper;
import com.lzke.ai.application.dto.UserPermission;
import com.lzke.ai.domain.entity.User;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class UserService {

    private static final Map<String, List<String>> ABILITY_MATRIX = Map.of(
            "admin", List.of("manage:all", "read:all", "update:all"),
            "user", List.of("read:tasks", "create:conversation", "read:documents"),
            "viewer", List.of("read:documents")
    );

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;

    public User authenticate(String username, String rawPassword) {
        var user = userMapper.findByUsername(username).orElseThrow(() ->
                new BusinessException(ErrorCode.ACCOUNT_NOT_FOUND));
        if (!"active".equalsIgnoreCase(user.getStatus())) {
            throw new BusinessException(ErrorCode.ACCOUNT_DISABLED);
        }
        if (user.getPasswordHash() == null || !passwordEncoder.matches(rawPassword, user.getPasswordHash())) {
            throw new BusinessException(ErrorCode.PASSWORD_INCORRECT);
        }
        return user;
    }

    public Optional<User> findById(String id) {
        return userMapper.findById(id);
    }

    public SimpleGrantedAuthority mapAuthority(String role) {
        return new SimpleGrantedAuthority("ROLE_" + role.toUpperCase());
    }

    public UserPermission buildPermission(User user) {
        return UserPermission.builder()
                .id(user.getId())
                .username(user.getUsername())
                .displayName(user.getDisplayName())
                .role(user.getRole())
                .abilities(ABILITY_MATRIX.getOrDefault(user.getRole(), List.of("read:documents")))
                .build();
    }

    public UserPermission buildPermission(String userId) {
        var user = userMapper.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ACCOUNT_NOT_FOUND));
        return buildPermission(user);
    }
}
