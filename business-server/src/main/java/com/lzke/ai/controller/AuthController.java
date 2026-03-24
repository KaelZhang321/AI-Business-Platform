package com.lzke.ai.controller;

import com.lzke.ai.application.dto.LoginRequest;
import com.lzke.ai.application.dto.LoginResponse;
import com.lzke.ai.application.dto.UserPermission;
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
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final UserService userService;
    private final JwtTokenProvider jwtTokenProvider;
    private final JwtProperties jwtProperties;

    @PostMapping("/login")
    @ResponseStatus(HttpStatus.OK)
    public LoginResponse login(@Valid @RequestBody LoginRequest request) {
        var user = userService.authenticate(request.getUsername(), request.getPassword());
        var accessToken = jwtTokenProvider.generateToken(user.getId(), user.getUsername(), user.getRole());
        var refreshToken = jwtTokenProvider.generateRefreshToken(user.getId(), user.getUsername(), user.getRole());
        var permission = userService.buildPermission(user);
        return new LoginResponse(accessToken, refreshToken, jwtProperties.getExpiration(), permission);
    }

    @PostMapping("/refresh")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> refresh(@RequestHeader("Authorization") String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "缺少 refresh token");
        }
        String refreshToken = authHeader.substring(7);
        try {
            Claims claims = jwtTokenProvider.parseClaims(refreshToken);
            if (!jwtTokenProvider.isRefreshToken(claims)) {
                throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "非有效的 refresh token");
            }
            UUID userId = UUID.fromString(claims.getSubject());
            String username = claims.get("username", String.class);
            String role = claims.get("role", String.class);
            String newAccessToken = jwtTokenProvider.generateToken(userId, username, role);
            return Map.of(
                    "token", newAccessToken,
                    "expiresIn", jwtProperties.getExpiration()
            );
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "refresh token 已过期或无效");
        }
    }

    @GetMapping("/me")
    public UserPermission me(Authentication authentication) {
        if (authentication == null || !(authentication.getPrincipal() instanceof UserPrincipal principal)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }
        return userService.buildPermission(principal.getId());
    }
}
