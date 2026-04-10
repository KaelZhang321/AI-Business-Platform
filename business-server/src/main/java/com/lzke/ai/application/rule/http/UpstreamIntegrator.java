package com.lzke.ai.application.rule.http;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.stream.Collectors;

/**
 * UpstreamIntegrator
 * 
 * A utility class to map local data structures to upstream HTTP requests
 * using Java 17's HttpClient and Jackson for JSON processing.
 */
public class UpstreamIntegrator {

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final HttpClient HTTP_CLIENT = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_2)
            .build();

    private static final String BASE_URL = "https://api.gateway.com/v1/users";

    // Target types for mapping
    public enum TargetType {
        HEADER,
        BODY_FIELD,
        QUERY_PARAM
    }

    // Mapping Rule definition
    public record MappingRule(String id, String sourcePath, TargetType targetType, String targetKey) {}

    /**
     * Executes the integration logic.
     * Maps the source map to an upstream request based on rules and sends it.
     */
    public void processAndSend(Map<String, Object> sourceData, String bearerToken) {
        List<MappingRule> rules = getConfigurationRules();
        
        try {
            HttpRequest request = buildRequest(sourceData, rules, bearerToken);
            System.out.println("Sending request to: " + request.uri());
            
            HttpResponse<String> response = HTTP_CLIENT.send(request, HttpResponse.BodyHandlers.ofString());
            
            System.out.println("Response Status Code: " + response.statusCode());
            System.out.println("Response Body: " + response.body());
            
        } catch (IOException | InterruptedException e) {
            System.err.println("Error during upstream integration: " + e.getMessage());
            Thread.currentThread().interrupt();
        } catch (Exception e) {
            System.err.println("Unexpected error: " + e.getMessage());
        }
    }

    /**
     * Constructs the HttpRequest object by applying mapping rules.
     */
    private HttpRequest buildRequest(Map<String, Object> sourceData, List<MappingRule> rules, String token) throws JsonProcessingException {
        HttpRequest.Builder requestBuilder = HttpRequest.newBuilder();
        
        Map<String, String> queryParams = new HashMap<>();
        Map<String, Object> bodyMap = new HashMap<>();

        // Add Auth Header
        requestBuilder.header("Authorization", "Bearer " + token);
        requestBuilder.header("Content-Type", "application/json");

        for (MappingRule rule : rules) {
            Object value = getValueByPath(sourceData, rule.sourcePath());
            
            if (value == null) {
                continue; // Skip if source data doesn't contain the path
            }

            switch (rule.targetType()) {
                case HEADER -> requestBuilder.header(rule.targetKey(), value.toString());
                case QUERY_PARAM -> queryParams.put(rule.targetKey(), value.toString());
                case BODY_FIELD -> setValueByPath(bodyMap, rule.targetKey(), value);
            }
        }

        // Finalize URI with Query Parameters
        String queryString = queryParams.entrySet().stream()
                .map(entry -> URLEncoder.encode(entry.getKey(), StandardCharsets.UTF_8) + "=" + 
                              URLEncoder.encode(entry.getValue(), StandardCharsets.UTF_8))
                .collect(Collectors.joining("&"));
        
        URI uri = URI.create(BASE_URL + (queryString.isEmpty() ? "" : "?" + queryString));

        // Finalize Body
        String jsonBody = OBJECT_MAPPER.writeValueAsString(bodyMap);

        return requestBuilder
                .uri(uri)
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                .build();
    }

    /**
     * Resolves a value from a nested map using dot notation (e.g., "user.email").
     */
    private Object getValueByPath(Map<String, Object> map, String path) {
        String[] keys = path.split("\\.");
        Object current = map;
        for (String key : keys) {
            if (current instanceof Map<?, ?> nestedMap) {
                current = nestedMap.get(key);
            } else {
                return null;
            }
        }
        return current;
    }

    /**
     * Sets a value in a nested map using dot notation (e.g., "meta.currentScore").
     * Creates intermediate maps if they don't exist.
     */
    @SuppressWarnings("unchecked")
    private void setValueByPath(Map<String, Object> map, String path, Object value) {
        String[] keys = path.split("\\.");
        Map<String, Object> current = map;
        for (int i = 0; i < keys.length - 1; i++) {
            current = (Map<String, Object>) current.computeIfAbsent(keys[i], k -> new HashMap<String, Object>());
        }
        current.put(keys[keys.length - 1], value);
    }

    /**
     * Defines the hardcoded configuration rules provided in the requirements.
     */
    private List<MappingRule> getConfigurationRules() {
        return List.of(
            new MappingRule("1", "user.id", TargetType.HEADER, "X-User-Reference"),
            new MappingRule("2", "user.email", TargetType.BODY_FIELD, "contactEmail"),
            new MappingRule("3", "data.score", TargetType.BODY_FIELD, "meta.currentScore"),
            new MappingRule("4", "eventId", TargetType.QUERY_PARAM, "traceId")
        );
    }

    /**
     * Demonstration of usage with sample input data.
     */
    public static void main(String[] args) {
        UpstreamIntegrator integrator = new UpstreamIntegrator();

        // Sample Input Data
        Map<String, Object> input = new HashMap<>();
        input.put("eventId", "evt_12345");
        input.put("timestamp", 1678900000);

        Map<String, Object> user = new HashMap<>();
        user.put("id", "u_999");
        user.put("name", "John Doe");
        user.put("email", "john@example.com");
        input.put("user", user);

        Map<String, Object> data = new HashMap<>();
        data.put("score", 85);
        data.put("active", true);
        input.put("data", data);

        // Execute integration
        // Note: This will attempt a real network call to api.gateway.com
        integrator.processAndSend(input, "sample_bearer_token_123");
    }
}
