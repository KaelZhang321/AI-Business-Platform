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
                null,
                null,
                mock(SemanticFieldDictMapper.class),
                mock(SemanticFieldAliasMapper.class),
                mock(SemanticFieldValueMapMapper.class)
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

    @Test
    void extractResponseExample_shouldParseMarkdownJsonBlockAndWrapResultEnvelope() throws Exception {
        JsonNode rootDocument = objectMapper.readTree("""
                {
                  "paths": {
                    "/dwCustomerArchive/identityContact": {
                      "post": {
                        "description": "响应：Result<IdentityContactPdfVO>\\n```json\\n{\\n  \\"customerName\\": \\"张三\\",\\n  \\"gender\\": \\"男\\",\\n  \\"age\\": 36\\n}\\n```",
                        "responses": {
                          "200": {
                            "content": {
                              "application/json": {
                                "schema": {
                                  "$ref": "#/components/schemas/ResultIdentityContactPdfVO"
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
                      "ResultIdentityContactPdfVO": {
                        "type": "object",
                        "properties": {
                          "success": {
                            "type": "boolean",
                            "default": true
                          },
                          "code": {
                            "type": "integer",
                            "default": 0
                          },
                          "result": {
                            "$ref": "#/components/schemas/IdentityContactPdfVO"
                          }
                        }
                      },
                      "IdentityContactPdfVO": {
                        "type": "object",
                        "properties": {
                          "customerName": {
                            "type": "string"
                          },
                          "gender": {
                            "type": "string"
                          },
                          "age": {
                            "type": "integer"
                          }
                        }
                      }
                    }
                  }
                }
                """);

        JsonNode operationNode = rootDocument.path("paths")
                .path("/dwCustomerArchive/identityContact")
                .path("post");
        JsonNode example = invokePrivateJsonNodeMethod("extractResponseExample", rootDocument, operationNode);

        assertNotNull(example);
        assertEquals(true, example.path("success").asBoolean());
        assertEquals(0, example.path("code").asInt());
        assertEquals("张三", example.path("result").path("customerName").asText());
        assertEquals("男", example.path("result").path("gender").asText());
        assertEquals(36, example.path("result").path("age").asInt());
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
