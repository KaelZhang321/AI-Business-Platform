package com.lzke.ai.application.ui;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import org.springframework.web.util.UriComponentsBuilder;
import org.springframework.web.util.UriUtils;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lecz.service.tools.core.dto.ResponseDto;
import com.lzke.ai.domain.entity.UiApiEndpoint;
import com.lzke.ai.domain.entity.UiApiSource;
import com.lzke.ai.security.UserPrincipal;

import jakarta.servlet.http.HttpServletRequest;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * UI Builder HTTP 调用工具服务。
 *
 * <p>该服务专门负责“根据接口源 + 接口定义发起真实 HTTP 调用”这件事，
 * 从 {@link UiBuilderApplicationService} 中抽离出以下通用能力：
 *
 * <ul>
 *     <li>拼装最终请求地址</li>
 *     <li>合并默认请求头、运行时请求头和认证头</li>
 *     <li>执行真实 HTTP 请求并统一封装请求/响应快照</li>
 * </ul>
 *
 * <p>这样 UI Builder 的应用服务只需要关心：
 *
 * <ul>
 *     <li>根据 ID 查出接口定义和接口源</li>
 *     <li>校验当前调用场景是否合法</li>
 *     <li>把执行结果写入联调日志或运行时日志</li>
 * </ul>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UiHttpInvokeService {
	
	private static final String OMS_OPENAPI_ = "oms_openapi";
    private static final String OMS_OPENAPI = "OMS";
    private static final Pattern PATH_VARIABLE_PATTERN = Pattern.compile("\\{([^/{}]+)}");
    private static final String OA_ACCESS_TOKEN_CACHE_KEY = "httpToken:oa:access_token:";
    private static final long OA_ACCESS_TOKEN_TTL_SECONDS = 3500L;
    private static final String OMS_OPEN_ID_CACHE_KEY_PREFIX = "httpToken:oms:open_id:employee:";
    private static final long OMS_OPEN_ID_TTL_SECONDS = 12 * 60 * 60L;
    private static final String OMS_OPEN_ID_URL = "/system/employee/sys-employee-bind/getOpenId";
    
    @Value("${forest.variables.oa.appCode}")
    private String appCode;

    @Value("${forest.variables.crm.services.oa.url}")
    private String iamUrl;

    private final ObjectMapper objectMapper;
    private final RestTemplate restTemplate;
    private final StringRedisTemplate stringRedisTemplate;

    /**
     * 发起一次真实 HTTP 调用，并把请求/响应快照统一封装成结果对象。
     *
     * @param source 接口源，提供基础地址、默认请求头和认证配置
     * @param endpoint 接口定义，提供 path、method 等基础信息
     * @param requestHeaders 本次调用额外传入的请求头
     * @param queryParams 本次调用的 Query 参数
     * @param requestBody 本次调用的请求体
     * @return 统一的调用结果对象
     */
    public HttpExecutionResult execute(
            UiApiSource source,
            UiApiEndpoint endpoint,
            Map<String, Object> requestHeaders,
            Map<String, Object> queryParams,
            Object requestBody
    ) {
        String requestUrl = buildRequestUrl(source, endpoint, queryParams, requestBody);
        HttpHeaders headers = buildRequestHeaders(source, requestHeaders);
        HttpMethod httpMethod = HttpMethod.valueOf(endpoint.getMethod());
        HttpEntity<Object> entity = new HttpEntity<>(requestBody, headers);

        try {
            ResponseEntity<String> response = restTemplate.exchange(requestUrl, httpMethod, entity, String.class);
            return new HttpExecutionResult(
                    requestUrl,
                    new LinkedHashMap<>(headers.toSingleValueMap()),
                    queryParams != null ? new LinkedHashMap<>(queryParams) : Collections.emptyMap(),
                    requestBody,
                    response.getStatusCode().value(),
                    new LinkedHashMap<>(response.getHeaders().toSingleValueMap()),
                    response.getBody(),
                    true,
                    null
            );
        } catch (RestClientException ex) {
            return new HttpExecutionResult(
                    requestUrl,
                    new LinkedHashMap<>(headers.toSingleValueMap()),
                    queryParams != null ? new LinkedHashMap<>(queryParams) : Collections.emptyMap(),
                    requestBody,
                    null,
                    Collections.emptyMap(),
                    null,
                    false,
                    ex.getMessage()
            );
        }
    }

    /**
     * 组装最终请求地址。
     *
     * <p>地址由 `baseUrl + path + queryParams + API Key(Query)` 共同组成。
     *
     * @param source 接口源
     * @param endpoint 接口定义
     * @param queryParams 调用时的查询参数
     * @return 最终请求地址
     */
    private String buildRequestUrl(UiApiSource source, UiApiEndpoint endpoint, Map<String, Object> queryParams, Object requestBody) {
        String baseUrl = defaultIfBlank(source.getBaseUrl(), "");
        String path = resolvePathVariables(defaultIfBlank(endpoint.getPath(), ""), queryParams, requestBody);
        UriComponentsBuilder builder = UriComponentsBuilder.fromUriString(baseUrl + path);
        Map<String, Object> safeQueryParams = queryParams != null ? new LinkedHashMap<>(queryParams) : new LinkedHashMap<>();
        removeResolvedPathVariables(safeQueryParams, defaultIfBlank(endpoint.getPath(), ""));
        safeQueryParams.forEach((key, value) -> {
            if (value instanceof Iterable<?> iterable) {
                for (Object item : iterable) {
                    builder.queryParam(key, item);
                }
            } else if (value != null) {
                builder.queryParam(key, value);
            }
        });

        Map<String, Object> authConfig = readMap(source.getAuthConfig());
        if ("api_key".equals(source.getAuthType()) && authConfig.containsKey("queryName") && authConfig.containsKey("queryValue")) {
            builder.queryParam(String.valueOf(authConfig.get("queryName")), authConfig.get("queryValue"));
        }
        return builder.build(true).toUriString();
    }

    /**
     * 把路径模板中的 `{variable}` 替换成实际值。
     *
     * <p>优先从 query 参数中取值；如果 query 中不存在，再尝试从请求体的顶层对象中取值。
     * 这样可以同时兼容：
     *
     * <ul>
     *     <li>`GET /user/{id}` + queryParams</li>
     *     <li>`POST /customer/{customerId}` + body 中携带 customerId</li>
     * </ul>
     *
     * @param rawPath 原始路径模板
     * @param queryParams 查询参数
     * @param requestBody 请求体
     * @return 替换后的路径
     */
    private String resolvePathVariables(String rawPath, Map<String, Object> queryParams, Object requestBody) {
        Matcher matcher = PATH_VARIABLE_PATTERN.matcher(rawPath);
        StringBuffer resolvedPath = new StringBuffer();
        Map<String, Object> bodyMap = requestBody instanceof Map<?, ?> map ? castToObjectMap(map) : Collections.emptyMap();

        while (matcher.find()) {
            String variableName = matcher.group(1);
            Object variableValue = queryParams != null ? queryParams.get(variableName) : null;
            if (variableValue == null) {
                variableValue = bodyMap.get(variableName);
            }
            if (variableValue == null) {
                continue;
            }
            matcher.appendReplacement(
                    resolvedPath,
                    Matcher.quoteReplacement(UriUtils.encodePathSegment(String.valueOf(variableValue), StandardCharsets.UTF_8))
            );
        }
        matcher.appendTail(resolvedPath);
        return resolvedPath.toString();
    }

    private void removeResolvedPathVariables(Map<String, Object> queryParams, String rawPath) {
        Matcher matcher = PATH_VARIABLE_PATTERN.matcher(rawPath);
        while (matcher.find()) {
            queryParams.remove(matcher.group(1));
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> castToObjectMap(Map<?, ?> source) {
        Map<String, Object> result = new LinkedHashMap<>();
        source.forEach((key, value) -> {
            if (key != null) {
                result.put(String.valueOf(key), value);
            }
        });
        return result;
    }

    /**
     * 组装最终请求头。
     *
     * <p>请求头来源按以下顺序叠加：
     *
     * <ol>
     *     <li>默认 Content-Type</li>
     *     <li>接口源默认请求头</li>
     *     <li>调用方显式传入的请求头</li>
     *     <li>接口源认证配置推导出的认证头</li>
     * </ol>
     *
     * @param source 接口源
     * @param requestHeaders 调用方传入的请求头
     * @return 最终请求头
     */
    private HttpHeaders buildRequestHeaders(UiApiSource source, Map<String, Object> requestHeaders) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        readMap(source.getDefaultHeaders()).forEach((key, value) -> headers.set(key, String.valueOf(value)));
        if (requestHeaders != null) {
            requestHeaders.forEach((key, value) -> headers.set(key, String.valueOf(value)));
        }

        Map<String, Object> authConfig = readMap(source.getAuthConfig());
        String authType = defaultIfBlank(source.getAuthType(), "none");
        switch (authType) {
            case "api_key" -> {
                if (authConfig.containsKey("headerName") && authConfig.containsKey("headerValue")) {
                    headers.set(String.valueOf(authConfig.get("headerName")), String.valueOf(authConfig.get("headerValue")));
                }
            }
            case "bearer_token" -> {
                if (authConfig.containsKey("token")) {
                    headers.setBearerAuth(String.valueOf(authConfig.get("token")));
                } else if (authConfig.containsKey("accessToken")) {
                    headers.setBearerAuth(String.valueOf(authConfig.get("accessToken")));
                }
            }
            case "basic_auth" -> {
                String username = String.valueOf(authConfig.getOrDefault("username", ""));
                String password = String.valueOf(authConfig.getOrDefault("password", ""));
                String encoded = Base64.getEncoder().encodeToString((username + ":" + password).getBytes(StandardCharsets.UTF_8));
                headers.set(HttpHeaders.AUTHORIZATION, "Basic " + encoded);
            }
            case "oauth2_client" -> {
            	
//            	if(source.getCode().equals(IAM_OPENAPI)||source.getCode().equals(CRM_OPENAPI)) {
            		 String accessToken = resolveOauth2ClientAccessToken(authConfig);
                     if (StringUtils.hasText(accessToken)) {
                         headers.setBearerAuth(accessToken);
                     }
                     applyOmsGatewayHeadersIfNecessary(source, headers);
//				}
            }
            default -> {
            }
        }
        return headers;
    }

    /**
     * 把 JSON 文本尽量解析成 Map；解析失败时返回空 Map，避免调用过程被无效配置中断。
     *
     * @param json JSON 字符串
     * @return 解析后的 Map
     */
    private Map<String, Object> readMap(String json) {
        if (!StringUtils.hasText(json)) {
            return new LinkedHashMap<>();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (Exception ex) {
            return new LinkedHashMap<>();
        }
    }

    private String defaultIfBlank(String value, String defaultValue) {
        return StringUtils.hasText(value) ? value : defaultValue;
    }

    /**
     * 获取 oauth2_client 类型接口源的访问令牌。
     *
     * <p>读取顺序如下：
     *
     * <ol>
     *     <li>先查 Redis 中的缓存 token</li>
     *     <li>若缓存不存在，则从 authConfig 中读取 `oauthUrl`、`appKey`、`appSecret` 发起 POST 请求</li>
     *     <li>按约定读取 `ResponseDto<String>.message` 作为 accessToken</li>
     *     <li>将 token 写回 Redis，TTL 为 3500 秒</li>
     * </ol>
     *
     * @param authConfig 接口源认证配置
     * @return accessToken；无法获取时返回 null
     */
    private String resolveOauth2ClientAccessToken(Map<String, Object> authConfig) {
        String cachedToken = stringRedisTemplate.opsForValue().get(OA_ACCESS_TOKEN_CACHE_KEY+appCode);
        if (StringUtils.hasText(cachedToken)) {
            return cachedToken;
        }

        String oauthUrl = authConfig.get("oauthUrl") != null ? String.valueOf(authConfig.get("oauthUrl")) : null;
        String appKey = authConfig.get("appKey") != null ? String.valueOf(authConfig.get("appKey")) : null;
        String appSecret = authConfig.get("appSecret") != null ? String.valueOf(authConfig.get("appSecret")) : null;
        if (!StringUtils.hasText(oauthUrl) || !StringUtils.hasText(appKey) || !StringUtils.hasText(appSecret)) {
            return null;
        }

        HttpHeaders oauthHeaders = new HttpHeaders();
        oauthHeaders.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(Map.of(
                "appKey", appKey,
                "appSecret", appSecret
        ), oauthHeaders);

        try {
            ResponseEntity<ResponseDto> responseEntity = restTemplate.exchange(
                    oauthUrl,
                    HttpMethod.POST,
                    requestEntity,
                    ResponseDto.class
            );
            ResponseDto<?> response = responseEntity.getBody();
            if (response == null || !StringUtils.hasText(response.getMessage())) {
                return null;
            }

            String accessToken = response.getMessage();
            stringRedisTemplate.opsForValue().set(
                    OA_ACCESS_TOKEN_CACHE_KEY+appCode,
                    accessToken,
                    OA_ACCESS_TOKEN_TTL_SECONDS,
                    TimeUnit.SECONDS
            );
            return accessToken;
        } catch (RestClientException ex) {
            return null;
        }
    }

    /**
     * 对接 OMS 网关时补充固定头。
     *
     * <p>当前约定：
     *
     * <ul>
     *     <li>`from=apigateway`</li>
     *     <li>`appcode=OMS`</li>
     *     <li>`userid=<当前登录员工在 OMS 中绑定的 openId>`</li>
     * </ul>
     *
     * <p>`userid` 并不是当前系统里的员工 ID，而是需要通过 IAM 接口
     * `getOpenId?appCode=OMS&employeeId=<当前用户ID>` 转换出来的 openId。
     * 该映射会写入 Redis，避免每次转发都回源查询。
     */
    private void applyOmsGatewayHeadersIfNecessary(UiApiSource source, HttpHeaders headers) {
        if (!OMS_OPENAPI_.equalsIgnoreCase(defaultIfBlank(source.getCode(), ""))) {
            return;
        }
        headers.set("from", "apigateway");
        headers.set("appcode", OMS_OPENAPI);

        String employeeId = resolveCurrentEmployeeId();
        if (!StringUtils.hasText(employeeId)) {
            return;
        }

        String openId = resolveOmsOpenId(source,employeeId);
        if (StringUtils.hasText(openId)) {
            headers.set("userid", openId);
        }
    }

    /**
     * 获取当前调用上下文里的员工 ID。
     *
     * <p>优先从 Spring Security 登录态中读取；如果当前接口没有走登录态，
     * 再退化到请求头 `X-User-Id` / `userid` 中查找。
     */
    private String resolveCurrentEmployeeId() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null && authentication.getPrincipal() instanceof UserPrincipal principal) {
            return principal.getId();
        }

        ServletRequestAttributes attributes = (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
        if (attributes == null) {
            return null;
        }
        HttpServletRequest request = attributes.getRequest();
        String headerUserId = request.getHeader("X-User-Id");
        if (StringUtils.hasText(headerUserId)) {
            return headerUserId;
        }
        String userId = request.getHeader("userid");
        return StringUtils.hasText(userId) ? userId : null;
    }

    /**
     * 根据当前员工 ID 获取其在 OMS 中绑定的 openId。
     *
     * <p>缓存策略：
     *
     * <ul>
     *     <li>`employeeId -> openId`</li>
     *     <li>`openId -> employeeId`</li>
     * </ul>
     *
     * <p>这样既能减少 OMS 回源压力，也便于后续按 openId 反查当前系统员工。
     */
    public String resolveOmsOpenId(UiApiSource source,String employeeId) {
        String cachedOpenId = stringRedisTemplate.opsForValue().get(OMS_OPEN_ID_CACHE_KEY_PREFIX + employeeId);
        if (StringUtils.hasText(cachedOpenId)) {
            return cachedOpenId;
        }

        String requestUrl = UriComponentsBuilder.fromUriString(iamUrl+OMS_OPEN_ID_URL)
                .queryParam("appCode", OMS_OPENAPI)
                .queryParam("employeeId", employeeId)
                .build(true)
                .toUriString();
        try {
        	HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            Map<String, Object> authConfig = readMap(source.getAuthConfig());
        	String accessToken = resolveOauth2ClientAccessToken(authConfig);
            if (StringUtils.hasText(accessToken)) {
                headers.setBearerAuth(accessToken);
            }
            ResponseEntity<ResponseDto> responseEntity = restTemplate.exchange(
                    requestUrl,
                    HttpMethod.GET,
                    new HttpEntity<>(headers),
                    ResponseDto.class
            );
            ResponseDto<?> response = responseEntity.getBody();
            if (response == null || !StringUtils.hasText(response.getMessage())) {
                return null;
            }
            String openId = response.getMessage();
            stringRedisTemplate.opsForValue().set(
                    OMS_OPEN_ID_CACHE_KEY_PREFIX + employeeId,
                    openId,
                    OMS_OPEN_ID_TTL_SECONDS,
                    TimeUnit.SECONDS
            );
            return openId;
        } catch (RestClientException ex) {
        	log.error("Failed to resolve OMS openId for employeeId={}", employeeId, ex);
            return null;
        }
    }

    /**
     * 一次 HTTP 调用的统一结果。
     *
     * <p>`responseBody` 保持原始字符串，由上层决定是否要继续做 JSON 解析，
     * 这样调用工具本身只负责传输层，不耦合 UI Builder 的业务语义。
     */
    public record HttpExecutionResult(
            String requestUrl,
            Map<String, Object> requestHeaders,
            Map<String, Object> queryParams,
            Object requestBody,
            Integer responseStatus,
            Map<String, Object> responseHeaders,
            Object responseBody,
            boolean success,
            String errorMessage
    ) {
    }
}
