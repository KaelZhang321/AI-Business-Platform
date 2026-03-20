package com.lzke.ai.security;

import lombok.AllArgsConstructor;
import lombok.Getter;
import org.springframework.security.core.GrantedAuthority;

import java.util.Collection;
import java.util.UUID;

@Getter
@AllArgsConstructor
public class UserPrincipal {
    private final UUID id;
    private final String username;
    private final String displayName;
    private final String role;
    private final Collection<? extends GrantedAuthority> authorities;
}
