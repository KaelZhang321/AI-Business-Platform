package com.lzke.ai.model.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;
import java.util.UUID;

@Getter
@Builder
public class UserPermission {
    private final UUID id;
    private final String username;
    private final String displayName;
    private final String role;
    private final List<String> abilities;
}
