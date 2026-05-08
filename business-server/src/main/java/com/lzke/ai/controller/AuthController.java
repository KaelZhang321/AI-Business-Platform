package com.lzke.ai.controller;

import java.time.Duration;
import java.util.List;
import java.util.Map;

import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lecz.iam.system.employee.dto.SysOauthCodeTokenDTO;
import com.lecz.iam.system.employee.dto.SysRoleQueryDTO;
import com.lecz.iam.system.employee.dto.SysTokenRefreshDTO;
import com.lecz.iam.system.employee.service.ISysEmployeeHttpService;
import com.lecz.iam.system.employee.service.ISysLoginHttpService;
import com.lecz.iam.system.employee.service.ISysMenuHttpService;
import com.lecz.iam.system.employee.service.ISysRoleHttpService;
import com.lecz.iam.system.employee.vo.SysEmployeeVO;
import com.lecz.iam.system.employee.vo.SysLoginResultVO;
import com.lecz.iam.system.employee.vo.SysMenuVO;
import com.lecz.iam.system.employee.vo.SysRoleVO;
import com.lecz.service.tools.core.dto.PageResponse;
import com.lecz.service.tools.core.dto.ResponseDto;
import com.lecz.service.tools.core.utils.AuthUtil;
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
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Tag(name = "认证", description = "JWT 登录/刷新/用户信息")
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

	private static final String DEVICE_ID = "pc";
    private static final String USER_INFO_CACHE_PREFIX = "auth:info:user:";
    private static final Duration USER_INFO_CACHE_TTL = Duration.ofHours(8);
	
    private final UserService userService;
    private final JwtTokenProvider jwtTokenProvider;
    private final JwtProperties jwtProperties;
    private final ObjectMapper objectMapper;
    private final StringRedisTemplate stringRedisTemplate;

    private final ISysLoginHttpService sysLoginHttpService;

    private final ISysEmployeeHttpService sysEmployeeHttpService;

    private final ISysRoleHttpService sysRoleHttpService;
    
    private final ISysMenuHttpService sysMenuHttpService;
    
    @Value("${forest.variables.oa.appCode}")
    private String appCode;
    

    @Operation(summary = "获取登陆的token", description = "获取登陆的token，返回 JWT 令牌")
    @GetMapping("/getAuthTokenByCode")
    @ResponseStatus(HttpStatus.OK)
    public LoginResponse getAuthTokenByCode(@RequestParam("code") String code) {

    	SysOauthCodeTokenDTO dto = new SysOauthCodeTokenDTO();
    	dto.setCode(code);
    	dto.setAppCode(appCode);
    	dto.setDeviceId(DEVICE_ID);
    	ResponseDto<SysLoginResultVO> result = sysLoginHttpService.oauthTokenByCode(dto);
    	log.info("获取登陆的token result: {}", result);
    	if(result.isSuccess()) {
    		SysLoginResultVO sysLoginResultVO = result.getData();
    		clearUserInfoCache(sysLoginResultVO.getAccountId());
    		getSysEmployeeVO(sysLoginResultVO.getAccountId()+"");
        	return new LoginResponse(sysLoginResultVO.getAccessToken(), sysLoginResultVO.getRefreshToken(), Long.parseLong(sysLoginResultVO.getAccessTokenExpiresIn()), null);
    	} else {
    		throw new BusinessException(ErrorCode.TOKEN_INVALID, result.getMessage());                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   
    	}
    
    }
    
    
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
    
    @Operation(summary = "获取当前用户信息", description = "返回当前登录用户的权限信息")
    @GetMapping("/info")
    public ResponseDto<SysEmployeeVO> info() {
    	Long userId = AuthUtil.getUserId();
    	return ResponseDto.success(getSysEmployeeVO(userId+""));
    }

    @Operation(summary = "按应用编码查询角色", description = "调用 IAM 角色中心的 list 接口，默认查询 AI-RND-WORKFLOW 下的角色")
    @GetMapping("/roles")
    public ResponseDto<PageResponse<SysRoleVO>> listRoles(
            @RequestParam(name = "appCode", defaultValue = "AI-RND-WORKFLOW") String roleAppCode,
            @RequestParam(name = "pageNo", defaultValue = "1") Integer pageNo,
            @RequestParam(name = "pageSize", defaultValue = "200") Integer pageSize
    ) {
        SysRoleQueryDTO queryDTO = new SysRoleQueryDTO();
        queryDTO.setAppCode(StringUtils.defaultIfBlank(roleAppCode, "AI-RND-WORKFLOW"));
        queryDTO.setPageNo(pageNo);
        queryDTO.setPageSize(pageSize);
        return sysRoleHttpService.list(queryDTO);
    }
    
    SysEmployeeVO getSysEmployeeVO(String userId) {
    	String employeeStr = stringRedisTemplate.opsForValue().get(USER_INFO_CACHE_PREFIX + userId);
    	if(StringUtils.isNotBlank(employeeStr)) {
			try {
				return objectMapper.readValue(employeeStr, SysEmployeeVO.class);
			} catch (JsonProcessingException e) {
				log.warn("用户信息从 Redis 反序列化失败, userId={}", userId, e);
				return null;
			}
		} else {
			ResponseDto<SysEmployeeVO> response = sysEmployeeHttpService.getById(Long.parseLong(userId));
            if (response != null && response.isSuccess() && response.getData() != null) {
                cacheUserInfo(userId, response.getData());
                return response.getData();
            }
    		
    	}
    	return null;
    }

    private void cacheUserInfo(String userId, SysEmployeeVO employee) {
        try {
            stringRedisTemplate.opsForValue().set(
                    USER_INFO_CACHE_PREFIX + userId,
                    objectMapper.writeValueAsString(employee),
                    USER_INFO_CACHE_TTL
            );
        } catch (JsonProcessingException ex) {
            log.warn("用户信息写入 Redis 失败, userId={}", userId, ex);
        }
    }

    private void clearUserInfoCache(String userId) {
        stringRedisTemplate.delete(USER_INFO_CACHE_PREFIX + userId);
    }
    
    @Operation(summary = "刷新令牌", description = "使用 refresh token 获取新的 access token")
    @PostMapping("/refreshAuthToken")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> refreshAuthToken(@RequestBody SysTokenRefreshDTO dto) {
        
        try {
        	dto.setAppCode(appCode);
        	ResponseDto<SysLoginResultVO> result = sysLoginHttpService.refreshAccessToken(dto);
        	return Map.of(
                    "token", result.getData().getAccessToken(),
                    "refreshToken", result.getData().getRefreshToken(),
                    "expiresIn", result.getData().getRefreshTokenExpiresIn());
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            throw new BusinessException(ErrorCode.TOKEN_EXPIRED, "refresh token 已过期或无效");
        } 
     } 
    
    //获取当前用户的菜单
    @GetMapping("/getEmployeeMenus")
    @ResponseStatus(HttpStatus.OK)
    public ResponseDto<List<SysMenuVO>> getEmployeeMenus() {
		return sysMenuHttpService.getEmployeeMenusForThird(appCode,AuthUtil.getUserId()+"");
	}
    
}
