package com.lzke.ai.model.dto;

import lombok.Getter;

@Getter
public class LoginResponse {
    private final String token;
    private final long expiresIn;
    private final UserPermission user;

    public LoginResponse(String token, long expiresIn, UserPermission user) {
        this.token = token;
        this.expiresIn = expiresIn;
        this.user = user;
    }
}
