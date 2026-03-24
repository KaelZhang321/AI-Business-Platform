package com.lzke.ai.controller;

import com.lzke.ai.application.dto.LoginRequest;
import com.lzke.ai.application.dto.LoginResponse;
import com.lzke.ai.application.dto.UserPermission;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import com.lzke.ai.security.JwtProperties;
import com.lzke.ai.security.JwtTokenProvider;
import com.lzke.ai.security.UserPrincipal;
import com.lzke.ai.service.UserService;
import io.jsonwebtoken.Claims;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;

import java.util.Map;

@Tag(name = "认证", description = "JWT 登录/刷新/用户信息")
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final UserService userService;
    private final JwtTokenProvider jwtTokenProvider;
    private final JwtProperties jwtProperties;

    @Operation(summary = "用户登录", description = "用户名密码登录，返回 JWT 令牌")
    @PostMapping("/login")
    @ResponseStatus(HttpStatus.OK)
    public LoginResponse login(@Valid @RequestBody LoginRequest request) {
        var user = userService.authenticate(request.getUsername(), request.getPassword());
        var accessToken = jwtTokenProvider.generateToken(user.getId(), user.getUsername(), user.getRole());
        var refreshToken = jwtTokenProvider.generateRefreshToken(user.getId(), user.getUsername(), user.getRole());
        var permission = userService.buildPermission(user);
        return new LoginResponse(accessToken, refreshToken, jwtProperties.getExpiration(), permission);
    }

    @Operation(summary = "刷新令牌", description = "使用 refresh token 获取新的 access token")
    @PostMapping("/refresh")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> refresh(@RequestHeader("Authorization") String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            throw new BusinessException(ErrorCode.REFRESH_TOKEN_INVALID, "缺少 refresh token");
        }
        String refreshToken = authHeader.substring(7);
        try {
            Claims claims = jwtTokenProvider.parseClaims(refreshToken);
            if (!jwtTokenProvider.isRefreshToken(claims)) {
                throw new BusinessException(ErrorCode.REFRESH_TOKEN_INVALID);
            }
            String userId = claims.getSubject();
            String username = claims.get("username", String.class);
            String role = claims.get("role", String.class);
            String newAccessToken = jwtTokenProvider.generateToken(userId, username, role);
            return Map.of(
                    "token", newAccessToken,
                    "expiresIn", jwtProperties.getExpiration()
            );
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.TOKEN_EXPIRED, "refresh token 已过期或无效");
        }
    }

    @Operation(summary = "获取当前用户信息", description = "返回当前登录用户的权限信息")
    @GetMapping("/me")
    public UserPermission me(Authentication authentication) {
        if (authentication == null || !(authentication.getPrincipal() instanceof UserPrincipal principal)) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED);
        }
        return userService.buildPermission(principal.getId());
    }
}
