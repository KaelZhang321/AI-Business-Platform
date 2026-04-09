package com.lzke.ai.application.ui;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.lzke.ai.application.dto.UiApiInvokeRequest;
import com.lzke.ai.application.dto.UiJsonRenderInvokeResponse;
import com.lzke.ai.application.dto.UiJsonRenderSubmitActionRequest;
import com.lzke.ai.application.dto.UiJsonRenderSubmitResponse;
import com.lzke.ai.application.dto.UiJsonRenderSubmitRequest;
import com.lzke.ai.domain.entity.SemanticFieldAlias;
import com.lzke.ai.domain.entity.SemanticFieldDict;
import com.lzke.ai.domain.entity.SemanticFieldValueMap;
import com.lzke.ai.domain.entity.UiApiEndpoint;
import com.lzke.ai.domain.entity.UiApiFlowLog;
import com.lzke.ai.domain.entity.UiApiSource;
import com.lzke.ai.infrastructure.persistence.mapper.SemanticFieldAliasMapper;
import com.lzke.ai.infrastructure.persistence.mapper.SemanticFieldDictMapper;
import com.lzke.ai.infrastructure.persistence.mapper.SemanticFieldValueMapMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiEndpointMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiEndpointRoleMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiFlowLogMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiSourceMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class UiJsonRenderTransformServiceTest {

    @Mock
    private UiHttpInvokeService uiHttpInvokeService;
    @Mock
    private UiApiEndpointMapper uiApiEndpointMapper;
    @Mock
    private UiApiEndpointRoleMapper uiApiEndpointRoleMapper;
    @Mock
    private UiApiSourceMapper uiApiSourceMapper;
    @Mock
    private UiApiFlowLogMapper uiApiFlowLogMapper;
    @Mock
    private SemanticFieldDictMapper semanticFieldDictMapper;
    @Mock
    private SemanticFieldAliasMapper semanticFieldAliasMapper;
    @Mock
    private SemanticFieldValueMapMapper semanticFieldValueMapMapper;

    private UiJsonRenderTransformService service;

    @BeforeEach
    void setUp() {
        service = new UiJsonRenderTransformService(
                new ObjectMapper(),
                uiHttpInvokeService,
                uiApiEndpointMapper,
                uiApiEndpointRoleMapper,
                uiApiSourceMapper,
                uiApiFlowLogMapper,
                semanticFieldDictMapper,
                semanticFieldAliasMapper,
                semanticFieldValueMapMapper
        );
    }

    @Test
    void invokeAndTransformResponse_shouldReturnResponseBodyAndJsonRender() {
        UiApiEndpoint endpoint = buildEndpoint("endpoint-query", "source-main", "GET", """
                {"fieldConfig":{"ignore":[],"passthrough":[],"groups":[],"render":[
                    {"rawKey":"$.data.userName","standardKey":"name","label":"姓名","type":"text"},
                    {"rawKey":"$.data.totalScore","standardKey":"score","label":"积分","type":"number"}
                ]}}
                """);
        UiApiSource source = buildSource("source-main");

        when(uiApiEndpointMapper.selectById("endpoint-query")).thenReturn(endpoint);
        when(uiApiSourceMapper.selectById("source-main")).thenReturn(source);
        when(semanticFieldAliasMapper.selectList(any())).thenReturn(List.of());
        when(semanticFieldValueMapMapper.selectList(any())).thenReturn(List.of());
        when(uiHttpInvokeService.execute(eq(source), eq(endpoint), any(), any(), any()))
                .thenReturn(new UiHttpInvokeService.HttpExecutionResult(
                        "http://example.test/user/detail",
                        Map.of(),
                        Map.of(),
                        null,
                        200,
                        Map.of(),
                        "{\"data\":{\"userName\":\"张三\",\"totalScore\":99}}",
                        true,
                        null
                ));
        when(uiApiFlowLogMapper.insert(org.mockito.ArgumentMatchers.<UiApiFlowLog>any())).thenAnswer(invocation -> {
            UiApiFlowLog log = invocation.getArgument(0);
            log.setId("flow-log-1");
            return 1;
        });

        UiApiInvokeRequest request = new UiApiInvokeRequest();
        request.setFlowNum("FLOW_RENDER_001");

        UiJsonRenderInvokeResponse response = service.invokeAndTransformResponse("endpoint-query", null, request);

        assertEquals("endpoint-query", response.getEndpointId());
        assertEquals("FLOW_RENDER_001", response.getFlowNum());
        assertEquals("flow-log-1", response.getFlowLogId());
        Map<?, ?> body = assertInstanceOf(Map.class, response.getResponseBody());
        assertEquals("张三", ((Map<?, ?>) body.get("data")).get("userName"));
        Map<?, ?> jsonRender = response.getJsonRender();
        assertEquals("page", jsonRender.get("root"));
        Map<?, ?> elements = assertInstanceOf(Map.class, jsonRender.get("elements"));
        assertTrue(elements.containsKey("page"));
        Map<?, ?> page = assertInstanceOf(Map.class, elements.get("page"));
        List<?> children = assertInstanceOf(List.class, page.get("children"));
        assertFalse(children.isEmpty());
    }

    @Test
    void transformResponseToJsonRender_shouldPreferPagedRecordsOverRawPayload() {
        UiApiEndpoint endpoint = buildEndpoint("endpoint-list", "source-main", "GET", """
                {
                  "fieldConfig": {
                    "view": {
                      "type": "list",
                      "dataPath": "$.data.records"
                    }
                  },
                  "actions": {
                    "rowActions": [
                      {
                        "key": "edit",
                        "label": "编辑",
                        "type": "openFormModal",
                        "detailEndpointId": "employee_detail",
                        "submitEndpointId": "employee_update",
                        "idField": "id"
                      }
                    ]
                  }
                }
                """);
        endpoint.setOperationSafety("list");
        when(uiApiEndpointMapper.selectById("endpoint-list")).thenReturn(endpoint);
        when(semanticFieldAliasMapper.selectList(any())).thenReturn(List.of());
        when(semanticFieldValueMapMapper.selectList(any())).thenReturn(List.of());

        Map<String, Object> responseBody = Map.of(
                "code", 200,
                "message", "success",
                "data", Map.of(
                        "records", List.of(
                                Map.of("id", "27391", "realName", "段延芳", "employeeNo", "ID004675"),
                                Map.of("id", "26665", "realName", "君", "employeeNo", "ID000018")
                        ),
                        "total", 4,
                        "size", 10,
                        "current", 1,
                        "pages", 1
                )
        );

        Map<String, Object> jsonRender = service.transformResponseToJsonRender("endpoint-list", responseBody);

        assertEquals("page", jsonRender.get("root"));
        Map<?, ?> elements = assertInstanceOf(Map.class, jsonRender.get("elements"));
        assertFalse(elements.keySet().stream().anyMatch(key -> String.valueOf(key).startsWith("rawPayload")));
        Map<?, ?> page = assertInstanceOf(Map.class, elements.get("page"));
        List<?> children = assertInstanceOf(List.class, page.get("children"));
        assertFalse(children.isEmpty());
        assertTrue(children.stream().anyMatch(child -> String.valueOf(child).startsWith("primaryList")));
        assertFalse(children.stream().anyMatch(child -> String.valueOf(child).startsWith("pageMetricCard")));
        String primaryListId = children.stream()
                .map(String::valueOf)
                .filter(child -> child.startsWith("primaryList"))
                .findFirst()
                .orElseThrow();
        Map<?, ?> primaryList = assertInstanceOf(Map.class, elements.get(primaryListId));
        Map<?, ?> props = assertInstanceOf(Map.class, primaryList.get("props"));
        Map<?, ?> pagination = assertInstanceOf(Map.class, props.get("pagination"));
        assertEquals(4L, pagination.get("total"));
        assertEquals(10, pagination.get("pageSize"));
        assertEquals(1, pagination.get("current"));
        List<?> rowActions = assertInstanceOf(List.class, props.get("rowActions"));
        assertEquals("编辑", assertInstanceOf(Map.class, rowActions.get(0)).get("label"));
    }

    @Test
    void transformResponseToJsonRender_shouldRenderDetailObjectInsteadOfRawPayload() {
        UiApiEndpoint endpoint = buildEndpoint("endpoint-detail", "source-main", "GET", """
                {
                  "fieldConfig": {
                    "view": {
                      "type": "detail",
                      "dataPath": "$.data"
                    }
                  },
                  "form": {
                    "title": "编辑员工",
                    "mode": "modal",
                    "submitLabel": "保存",
                    "submitAction": {
                      "endpointId": "employee_update"
                    },
                    "fields": [
                      { "standardKey": "realName", "label": "姓名", "type": "text", "required": true },
                      { "standardKey": "mobile", "label": "手机号", "type": "text" },
                      { "standardKey": "gender", "label": "性别", "type": "select" },
                      { "standardKey": "status", "label": "状态", "type": "select" }
                    ]
                  }
                }
                """);
        endpoint.setOperationSafety("query");
        when(uiApiEndpointMapper.selectById("endpoint-detail")).thenReturn(endpoint);
        when(semanticFieldDictMapper.selectList(any())).thenReturn(List.of(
                buildSemanticDict("gender", "性别", "select", "{\"1\":\"男\",\"2\":\"女\"}"),
                buildSemanticDict("status", "状态", "select", "{\"0\":\"禁用\",\"1\":\"启用\"}")
        ));
        when(semanticFieldAliasMapper.selectList(any())).thenReturn(List.of(
                buildAlias("endpoint-detail", "realName", "realName"),
                buildAlias("endpoint-detail", "username", "username"),
                buildAlias("endpoint-detail", "mobile", "mobile"),
                buildAlias("endpoint-detail", "gender", "gender"),
                buildAlias("endpoint-detail", "status", "status")
        ));
        when(semanticFieldValueMapMapper.selectList(any())).thenReturn(List.of());

        Map<String, Object> responseBody = Map.of(
                "code", 200,
                "message", "success",
                "data", Map.of(
                        "id", "27826",
                        "username", "202503052",
                        "realName", "杨旭阳",
                        "mobile", "133****8963",
                        "gender", 2,
                        "status", 1
                )
        );

        Map<String, Object> jsonRender = service.transformResponseToJsonRender("endpoint-detail", responseBody);

        Map<?, ?> elements = assertInstanceOf(Map.class, jsonRender.get("elements"));
        assertFalse(elements.keySet().stream().anyMatch(key -> String.valueOf(key).startsWith("rawPayload")));
        Map<?, ?> page = assertInstanceOf(Map.class, elements.get("page"));
        List<?> children = assertInstanceOf(List.class, page.get("children"));
        assertTrue(children.stream().map(String::valueOf).anyMatch(child -> child.startsWith("detailTable")));

        String detailTableId = children.stream()
                .map(String::valueOf)
                .filter(child -> child.startsWith("detailTable"))
                .findFirst()
                .orElseThrow();
        Map<?, ?> detailTable = assertInstanceOf(Map.class, elements.get(detailTableId));
        Map<?, ?> props = assertInstanceOf(Map.class, detailTable.get("props"));
        List<?> rows = assertInstanceOf(List.class, props.get("data"));
        assertTrue(rows.stream().anyMatch(row -> String.valueOf(row).contains("杨旭阳")));

        String formId = children.stream()
                .map(String::valueOf)
                .filter(child -> child.startsWith("form"))
                .findFirst()
                .orElseThrow();
        Map<?, ?> form = assertInstanceOf(Map.class, elements.get(formId));
        Map<?, ?> formProps = assertInstanceOf(Map.class, form.get("props"));
        assertEquals("编辑员工", formProps.get("title"));
        assertEquals("保存", formProps.get("submitLabel"));
        Map<?, ?> initialValues = assertInstanceOf(Map.class, formProps.get("initialValues"));
        assertEquals("杨旭阳", initialValues.get("realName"));
        List<?> formFields = assertInstanceOf(List.class, formProps.get("fields"));
        Map<?, ?> genderField = formFields.stream()
                .map(Map.class::cast)
                .filter(field -> "gender".equals(field.get("standardKey")))
                .findFirst()
                .orElseThrow();
        List<?> genderOptions = assertInstanceOf(List.class, genderField.get("options"));
        assertFalse(genderOptions.isEmpty());
    }

    @Test
    void invokeAndTransformResponse_shouldExposePaginationBodyMappingForPostEndpoint() {
        UiApiEndpoint endpoint = buildEndpoint("endpoint-list-render", "source-main", "POST", """
                {"fieldConfig":{"pagination":{"currentKey":"pageNo","sizeKey":"pageSize","requestTarget":"body"}}}
                """);
        endpoint.setOperationSafety("list");
        UiApiSource source = buildSource("source-main");

        when(uiApiEndpointMapper.selectById("endpoint-list-render")).thenReturn(endpoint);
        when(uiApiSourceMapper.selectById("source-main")).thenReturn(source);
        when(semanticFieldAliasMapper.selectList(any())).thenReturn(List.of());
        when(semanticFieldValueMapMapper.selectList(any())).thenReturn(List.of());
        when(uiHttpInvokeService.execute(eq(source), eq(endpoint), any(), any(), any()))
                .thenReturn(new UiHttpInvokeService.HttpExecutionResult(
                        "http://example.test/endpoint-list-render",
                        Map.of(),
                        Map.of(),
                        "{\"keyword\":\"alice\",\"pageNo\":1,\"pageSize\":10}",
                        200,
                        Map.of(),
                        """
                        {"code":0,"data":{"size":10,"pages":1,"total":1,"current":1,"records":[{"id":1,"username":"alice","realName":"Alice Chen"}]}}
                        """,
                        true,
                        null
                ));
        when(uiApiFlowLogMapper.insert(org.mockito.ArgumentMatchers.<UiApiFlowLog>any())).thenAnswer(invocation -> {
            UiApiFlowLog log = invocation.getArgument(0);
            log.setId("flow-log-pagination");
            return 1;
        });

        UiApiInvokeRequest request = new UiApiInvokeRequest();
        request.setFlowNum("FLOW_PAGE_001");
        request.setBody(Map.of("keyword", "alice", "pageNo", 1, "pageSize", 10));

        UiJsonRenderInvokeResponse response = service.invokeAndTransformResponse("endpoint-list-render", null, request);

        Map<?, ?> elements = assertInstanceOf(Map.class, response.getJsonRender().get("elements"));
        Map<?, ?> page = assertInstanceOf(Map.class, elements.get("page"));
        List<?> children = assertInstanceOf(List.class, page.get("children"));
        String primaryListId = children.stream()
                .map(String::valueOf)
                .filter(child -> child.startsWith("primaryList"))
                .findFirst()
                .orElseThrow();
        Map<?, ?> primaryList = assertInstanceOf(Map.class, elements.get(primaryListId));
        Map<?, ?> props = assertInstanceOf(Map.class, primaryList.get("props"));
        Map<?, ?> pagination = assertInstanceOf(Map.class, props.get("pagination"));
        Map<?, ?> action = assertInstanceOf(Map.class, pagination.get("action"));

        assertEquals("pageNo", action.get("currentKey"));
        assertEquals("pageSize", action.get("sizeKey"));
        assertEquals("body", action.get("requestTarget"));
        Map<?, ?> actionBody = assertInstanceOf(Map.class, action.get("body"));
        assertEquals("alice", actionBody.get("keyword"));
        assertEquals(1, actionBody.get("pageNo"));
        assertEquals(10, actionBody.get("pageSize"));
    }

    @Test
    void invokeAndTransformResponse_shouldFallbackToPostListPaginationBinding() {
        UiApiEndpoint endpoint = buildEndpoint("endpoint-list-render-fallback", "source-main", "POST", null);
        endpoint.setOperationSafety("list");
        UiApiSource source = buildSource("source-main");

        when(uiApiEndpointMapper.selectById("endpoint-list-render-fallback")).thenReturn(endpoint);
        when(uiApiSourceMapper.selectById("source-main")).thenReturn(source);
        when(semanticFieldAliasMapper.selectList(any())).thenReturn(List.of());
        when(semanticFieldValueMapMapper.selectList(any())).thenReturn(List.of());
        when(uiHttpInvokeService.execute(eq(source), eq(endpoint), any(), any(), any()))
                .thenReturn(new UiHttpInvokeService.HttpExecutionResult(
                        "http://example.test/endpoint-list-render-fallback",
                        Map.of(),
                        Map.of(),
                        "{\"keyword\":\"alice\"}",
                        200,
                        Map.of(),
                        """
                        {"code":0,"data":{"size":10,"pages":1,"total":1,"current":1,"records":[{"id":1,"username":"alice"}]}}
                        """,
                        true,
                        null
                ));
        when(uiApiFlowLogMapper.insert(org.mockito.ArgumentMatchers.<UiApiFlowLog>any())).thenAnswer(invocation -> {
            UiApiFlowLog log = invocation.getArgument(0);
            log.setId("flow-log-pagination-fallback");
            return 1;
        });

        UiJsonRenderInvokeResponse response = service.invokeAndTransformResponse("endpoint-list-render-fallback", null, new UiApiInvokeRequest());

        Map<?, ?> elements = assertInstanceOf(Map.class, response.getJsonRender().get("elements"));
        Map<?, ?> page = assertInstanceOf(Map.class, elements.get("page"));
        List<?> children = assertInstanceOf(List.class, page.get("children"));
        String primaryListId = children.stream()
                .map(String::valueOf)
                .filter(child -> child.startsWith("primaryList"))
                .findFirst()
                .orElseThrow();
        Map<?, ?> primaryList = assertInstanceOf(Map.class, elements.get(primaryListId));
        Map<?, ?> props = assertInstanceOf(Map.class, primaryList.get("props"));
        Map<?, ?> pagination = assertInstanceOf(Map.class, props.get("pagination"));
        Map<?, ?> action = assertInstanceOf(Map.class, pagination.get("action"));

        assertEquals("pageNo", action.get("currentKey"));
        assertEquals("pageSize", action.get("sizeKey"));
        assertEquals("body", action.get("requestTarget"));
    }

    @Test
    void submitSemanticForm_shouldConvertSemanticValuesForMultipleEndpoints() {
        UiApiEndpoint firstEndpoint = buildEndpoint("endpoint-submit-1", "source-main", "POST", null);
        firstEndpoint.setSampleRequest("{}");
        UiApiEndpoint secondEndpoint = buildEndpoint("endpoint-submit-2", "source-main", "GET", null);
        UiApiSource source = buildSource("source-main");

        when(uiApiEndpointMapper.selectById("endpoint-submit-1")).thenReturn(firstEndpoint);
        when(uiApiEndpointMapper.selectById("endpoint-submit-2")).thenReturn(secondEndpoint);
        when(uiApiSourceMapper.selectById("source-main")).thenReturn(source);
        when(semanticFieldAliasMapper.selectList(any()))
                .thenReturn(List.of(buildAlias("endpoint-submit-1", "sex", "gender")))
                .thenReturn(List.of(buildAlias("endpoint-submit-2", "userName", "name")));
        when(semanticFieldValueMapMapper.selectList(any()))
                .thenReturn(List.of(buildValueMap("endpoint-submit-1", "gender", "男", "1")))
                .thenReturn(List.of());

        AtomicInteger logCounter = new AtomicInteger(1);
        when(uiApiFlowLogMapper.insert(org.mockito.ArgumentMatchers.<UiApiFlowLog>any())).thenAnswer(invocation -> {
            UiApiFlowLog log = invocation.getArgument(0);
            log.setId("flow-log-" + logCounter.getAndIncrement());
            return 1;
        });

        when(uiHttpInvokeService.execute(eq(source), eq(firstEndpoint), any(), any(), any()))
                .thenReturn(new UiHttpInvokeService.HttpExecutionResult(
                        "http://example.test/form/first",
                        Map.of(),
                        Map.of(),
                        "{\"sex\":\"1\"}",
                        200,
                        Map.of(),
                        "{\"success\":true}",
                        true,
                        null
                ));
        when(uiHttpInvokeService.execute(eq(source), eq(secondEndpoint), any(), any(), any()))
                .thenReturn(new UiHttpInvokeService.HttpExecutionResult(
                        "http://example.test/form/second?userName=%E5%BC%A0%E4%B8%89",
                        Map.of(),
                        Map.of("userName", "张三"),
                        null,
                        200,
                        Map.of(),
                        "{\"success\":true}",
                        true,
                        null
                ));

        UiJsonRenderSubmitActionRequest firstAction = new UiJsonRenderSubmitActionRequest();
        firstAction.setEndpointId("endpoint-submit-1");
        firstAction.setBodyKeys(List.of("sex"));

        UiJsonRenderSubmitActionRequest secondAction = new UiJsonRenderSubmitActionRequest();
        secondAction.setEndpointId("endpoint-submit-2");
        secondAction.setQueryKeys(List.of("userName"));

        UiJsonRenderSubmitRequest request = new UiJsonRenderSubmitRequest();
        request.setFlowNum("FLOW_FORM_001");
        request.setSemanticValues(Map.of("gender", "男", "name", "张三"));
        request.setActions(List.of(firstAction, secondAction));

        UiJsonRenderSubmitResponse response = service.submitSemanticForm(request);

        assertTrue(response.isSuccess());
        assertEquals(2, response.getResults().size());

        ArgumentCaptor<Object> bodyCaptor = ArgumentCaptor.forClass(Object.class);
        ArgumentCaptor<Map<String, Object>> queryCaptor = ArgumentCaptor.forClass(Map.class);
        verify(uiHttpInvokeService).execute(eq(source), eq(firstEndpoint), any(), queryCaptor.capture(), bodyCaptor.capture());
        Map<?, ?> firstBody = assertInstanceOf(Map.class, bodyCaptor.getValue());
        assertEquals("1", firstBody.get("sex"));

        ArgumentCaptor<Map<String, Object>> secondQueryCaptor = ArgumentCaptor.forClass(Map.class);
        verify(uiHttpInvokeService).execute(eq(source), eq(secondEndpoint), any(), secondQueryCaptor.capture(), any());
        assertEquals("张三", secondQueryCaptor.getValue().get("userName"));
    }

    private UiApiEndpoint buildEndpoint(String endpointId, String sourceId, String method, String fieldOrchestration) {
        UiApiEndpoint endpoint = new UiApiEndpoint();
        endpoint.setId(endpointId);
        endpoint.setSourceId(sourceId);
        endpoint.setName(endpointId);
        endpoint.setPath("/" + endpointId);
        endpoint.setMethod(method);
        endpoint.setSummary(endpointId + " summary");
        endpoint.setStatus("active");
        endpoint.setFieldOrchestration(fieldOrchestration);
        return endpoint;
    }

    private UiApiSource buildSource(String sourceId) {
        UiApiSource source = new UiApiSource();
        source.setId(sourceId);
        source.setBaseUrl("http://example.test");
        source.setStatus("active");
        source.setAuthType("none");
        return source;
    }

    private SemanticFieldAlias buildAlias(String endpointId, String aliasName, String standardKey) {
        SemanticFieldAlias alias = new SemanticFieldAlias();
        alias.setApiId(endpointId);
        alias.setAlias(aliasName);
        alias.setStandardKey(standardKey);
        return alias;
    }

    private SemanticFieldValueMap buildValueMap(String endpointId, String standardKey, String standardValue, String rawValue) {
        SemanticFieldValueMap valueMap = new SemanticFieldValueMap();
        valueMap.setApiId(endpointId);
        valueMap.setStandardKey(standardKey);
        valueMap.setStandardValue(standardValue);
        valueMap.setRawValue(rawValue);
        return valueMap;
    }

    private SemanticFieldDict buildSemanticDict(String standardKey, String label, String fieldType, String valueMap) {
        SemanticFieldDict dict = new SemanticFieldDict();
        dict.setStandardKey(standardKey);
        dict.setLabel(label);
        dict.setFieldType(fieldType);
        dict.setValueMap(valueMap);
        dict.setIsActive(1);
        return dict;
    }
}
