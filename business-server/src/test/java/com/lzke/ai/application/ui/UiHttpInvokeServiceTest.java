package com.lzke.ai.application.ui;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lzke.ai.domain.entity.UiApiEndpoint;
import com.lzke.ai.domain.entity.UiApiSource;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class UiHttpInvokeServiceTest {

    private RestTemplate restTemplate;
    private UiHttpInvokeService service;

    @BeforeEach
    void setUp() {
        restTemplate = mock(RestTemplate.class);
        service = new UiHttpInvokeService(new ObjectMapper(), restTemplate, mock(StringRedisTemplate.class));
    }

    @Test
    void execute_shouldReplacePathVariableFromQueryParamsAndAvoidDuplicateQueryParam() {
        UiApiSource source = buildSource("http://example.test");
        UiApiEndpoint endpoint = buildEndpoint("GET", "/customerInquiry/getGroupById/{customerId}");

        when(restTemplate.exchange(any(String.class), eq(HttpMethod.GET), any(HttpEntity.class), eq(String.class)))
                .thenReturn(ResponseEntity.ok("{}"));

        service.execute(
                source,
                endpoint,
                Map.of(),
                Map.of("customerId", "C1001", "tenantId", "T1"),
                null
        );

        ArgumentCaptor<String> urlCaptor = ArgumentCaptor.forClass(String.class);
        verify(restTemplate).exchange(urlCaptor.capture(), eq(HttpMethod.GET), any(HttpEntity.class), eq(String.class));
        assertEquals(
                "http://example.test/customerInquiry/getGroupById/C1001?tenantId=T1",
                urlCaptor.getValue()
        );
    }

    @Test
    void execute_shouldReplacePathVariableFromRequestBodyWhenQueryParamMissing() {
        UiApiSource source = buildSource("http://example.test");
        UiApiEndpoint endpoint = buildEndpoint("POST", "/customerInquiry/getGroupById/{customerId}");

        when(restTemplate.exchange(any(String.class), eq(HttpMethod.POST), any(HttpEntity.class), eq(String.class)))
                .thenReturn(ResponseEntity.ok("{}"));

        service.execute(
                source,
                endpoint,
                Map.of(),
                Map.of("tenantId", "T1"),
                Map.of("customerId", "C2002", "name", "alice")
        );

        ArgumentCaptor<String> urlCaptor = ArgumentCaptor.forClass(String.class);
        verify(restTemplate).exchange(urlCaptor.capture(), eq(HttpMethod.POST), any(HttpEntity.class), eq(String.class));
        assertEquals(
                "http://example.test/customerInquiry/getGroupById/C2002?tenantId=T1",
                urlCaptor.getValue()
        );
    }

    private UiApiSource buildSource(String baseUrl) {
        UiApiSource source = new UiApiSource();
        source.setBaseUrl(baseUrl);
        source.setAuthType("none");
        source.setDefaultHeaders("{}");
        source.setAuthConfig("{}");
        return source;
    }

    private UiApiEndpoint buildEndpoint(String method, String path) {
        UiApiEndpoint endpoint = new UiApiEndpoint();
        endpoint.setMethod(method);
        endpoint.setPath(path);
        return endpoint;
    }
}
