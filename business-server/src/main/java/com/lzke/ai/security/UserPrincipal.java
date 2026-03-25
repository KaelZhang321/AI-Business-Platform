package com.lzke.ai.security;

import lombok.AllArgsConstructor;
import lombok.Getter;
import org.springframework.security.core.GrantedAuthority;

import java.util.Collection;

@Getter
@AllArgsConstructor
public class UserPrincipal {
    private final String id;
    private final String username;
    private final String displayName;
    private final String role;
    private final Collection<? extends GrantedAuthority> authorities;
}
