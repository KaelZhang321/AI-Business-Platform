package com.lzke.ai.application.dto;

import lombok.Getter;

@Getter
public class LoginResponse {
    private final String token;
    private final String refreshToken;
    private final long expiresIn;
    private final UserPermission user;

    public LoginResponse(String token, String refreshToken, long expiresIn, UserPermission user) {
        this.token = token;
        this.refreshToken = refreshToken;
        this.expiresIn = expiresIn;
        this.user = user;
    }
}
