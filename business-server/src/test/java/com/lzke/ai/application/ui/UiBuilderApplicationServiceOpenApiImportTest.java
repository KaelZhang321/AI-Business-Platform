package com.lzke.ai.application.ui;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lzke.ai.infrastructure.persistence.mapper.SemanticFieldAliasMapper;
import com.lzke.ai.infrastructure.persistence.mapper.SemanticFieldDictMapper;
import com.lzke.ai.infrastructure.persistence.mapper.SemanticFieldValueMapMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiEndpointMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiEndpointRoleMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiFlowLogMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiSourceMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiTagMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiApiTestLogMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiNodeBindingMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiPageMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiPageNodeMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiProjectMapper;
import com.lzke.ai.infrastructure.persistence.mapper.UiSpecVersionMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestTemplate;

import java.lang.reflect.Method;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.Mockito.mock;

class UiBuilderApplicationServiceOpenApiImportTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private UiBuilderApplicationService service;

    @BeforeEach
    void setUp() {
        service = new UiBuilderApplicationService(
                objectMapper,
                mock(RestTemplate.class),
                mock(UiBuilderMetadataService.class),
                mock(UiHttpInvokeService.class),
                mock(UiJsonRenderTransformService.class),
                mock(UiApiSourceMapper.class),
                mock(UiApiTagMapper.class),
                mock(UiApiEndpointMapper.class),
                mock(UiApiEndpointRoleMapper.class),
                mock(UiApiFlowLogMapper.class),
                mock(UiApiTestLogMapper.class),
                mock(SemanticFieldDictMapper.class),
                mock(SemanticFieldAliasMapper.class),
                mock(SemanticFieldValueMapMapper.class),
                mock(UiProjectMapper.class),
                mock(UiPageMapper.class),
                mock(UiPageNodeMapper.class),
                mock(UiNodeBindingMapper.class),
                mock(UiSpecVersionMapper.class)
        );
    }

    @Test
    void extractResponseSchema_shouldResolveUrlEncodedSchemaReference() throws Exception {
        JsonNode rootDocument = objectMapper.readTree("""
                {
                  "paths": {
                    "/customerInquiry/getCustBasicInfoById": {
                      "get": {
                        "responses": {
                          "200": {
                            "content": {
                              "application/json": {
                                "schema": {
                                  "$ref": "#/components/schemas/Result%C2%ABCustBasicInfoVO%C2%BB"
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                  },
                  "components": {
                    "schemas": {
                      "Result«CustBasicInfoVO»": {
                        "type": "object",
                        "properties": {
                          "code": {
                            "type": "integer"
                          },
                          "result": {
                            "$ref": "#/components/schemas/CustBasicInfoVO"
                          }
                        }
                      },
                      "CustBasicInfoVO": {
                        "type": "object",
                        "properties": {
                          "id": {
                            "type": "string"
                          },
                          "name": {
                            "type": "string"
                          },
                          "phone": {
                            "type": "string"
                          }
                        }
                      }
                    }
                  }
                }
                """);

        JsonNode operationNode = rootDocument.path("paths")
                .path("/customerInquiry/getCustBasicInfoById")
                .path("get");
        JsonNode schema = invokeExtractResponseSchema(rootDocument, operationNode);

        assertNotNull(schema);
        assertEquals("object", schema.path("type").asText());
        assertEquals("integer", schema.path("properties").path("code").path("type").asText());
        assertEquals("object", schema.path("properties").path("result").path("type").asText());
        assertEquals("string", schema.path("properties").path("result").path("properties").path("id").path("type").asText());
        assertEquals("string", schema.path("properties").path("result").path("properties").path("name").path("type").asText());
        assertEquals("string", schema.path("properties").path("result").path("properties").path("phone").path("type").asText());
    }

    @Test
    void extractRequestSchema_shouldParseQueryParametersWhenRequestBodyMissing() throws Exception {
        JsonNode rootDocument = objectMapper.readTree("""
                {
                  "paths": {
                    "/customerInquiry/getCustBasicInfoById": {
                      "get": {
                        "parameters": [
                          {
                            "name": "id",
                            "in": "query",
                            "required": true,
                            "schema": {
                              "type": "string"
                            }
                          }
                        ]
                      }
                    }
                  }
                }
                """);

        JsonNode operationNode = rootDocument.path("paths")
                .path("/customerInquiry/getCustBasicInfoById")
                .path("get");
        JsonNode schema = invokePrivateJsonNodeMethod("extractRequestSchema", rootDocument, operationNode);
        JsonNode example = invokePrivateJsonNodeMethod("extractRequestExample", rootDocument, operationNode);

        assertNotNull(schema);
        assertEquals("object", schema.path("type").asText());
        assertEquals("string", schema.path("properties").path("id").path("type").asText());
        assertEquals("query", schema.path("properties").path("id").path("x-in").asText());
        assertEquals("id", schema.path("required").get(0).asText());

        assertNotNull(example);
        assertEquals("", example.path("id").asText());
    }

    private JsonNode invokeExtractResponseSchema(JsonNode rootDocument, JsonNode operationNode) throws Exception {
        return invokePrivateJsonNodeMethod("extractResponseSchema", rootDocument, operationNode);
    }

    private JsonNode invokePrivateJsonNodeMethod(String methodName, JsonNode rootDocument, JsonNode operationNode) throws Exception {
        Method method = UiBuilderApplicationService.class.getDeclaredMethod(
                methodName,
                JsonNode.class,
                JsonNode.class
        );
        method.setAccessible(true);
        return (JsonNode) method.invoke(service, rootDocument, operationNode);
    }
}
