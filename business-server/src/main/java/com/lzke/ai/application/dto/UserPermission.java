package com.lzke.ai.application.dto;

import lombok.Builder;
import lombok.Getter;

import java.util.List;

@Getter
@Builder
public class UserPermission {
    private final String id;
    private final String username;
    private final String displayName;
    private final String role;
    private final List<String> abilities;
}
