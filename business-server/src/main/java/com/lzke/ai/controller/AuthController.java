package com.lzke.ai.controller;

import com.lzke.ai.model.dto.LoginRequest;
import com.lzke.ai.model.dto.LoginResponse;
import com.lzke.ai.model.dto.UserPermission;
import com.lzke.ai.security.JwtProperties;
import com.lzke.ai.security.JwtTokenProvider;
import com.lzke.ai.security.UserPrincipal;
import com.lzke.ai.service.UserService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

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
        var token = jwtTokenProvider.generateToken(user.getId(), user.getUsername(), user.getRole());
        var permission = userService.buildPermission(user);
        return new LoginResponse(token, jwtProperties.getExpiration(), permission);
    }

    @GetMapping("/me")
    public UserPermission me(Authentication authentication) {
        if (authentication == null || !(authentication.getPrincipal() instanceof UserPrincipal principal)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "未登录");
        }
        return userService.buildPermission(principal.getId());
    }
}
