package com.lzke.ai.application.rule;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import com.google.common.collect.Lists;

import jakarta.servlet.http.HttpServletRequest;

public class HttpRequestNode extends RuleNode {

	private String nodeConfig;
	private RestTemplate restTemplate;

	// Target types for mapping
	public enum TargetType {
		HEADER, BODY, QUERY
	}

	// Mapping Rule definition
	public record MappingRule(String id, String sourcePath, TargetType targetType, String targetKey) {
	}

	public HttpRequestNode(String nodeId, RestTemplate restTemplate, String nodeConfig) {
		super(nodeId);
		this.nodeConfig = nodeConfig;
		this.restTemplate = restTemplate;
	}

	public HttpRequestNode(String nodeId, Integer nodeGroup, RestTemplate restTemplate, String nodeConfig) {
		super(nodeId, nodeGroup);
		this.nodeConfig = nodeConfig;
		this.restTemplate = restTemplate;
	}

	// {"httpMethod":"GET","url":"
	// https://beta-intel.kaibol.net/prod-api/bservice/wxCP/callback","timeout":30,
	// "httpParams":[{"sourceParam":"test","paramType":"query","targetKey":"t"}],"resultKey":"res"}
	@Override
	public Map<String, Object> execute(Map<String, Object> input) throws Exception {

		JSONObject config = JSON.parseObject(nodeConfig);
		String httpMethod = config.getString("httpMethod");
		String url = config.getString("url");
		String resultKey = config.getString("resultKey");

		JSONArray paramArray = config.getJSONArray("httpParams");
		List<MappingRule> rules = Lists.newArrayList();
		if (paramArray != null && paramArray.size() > 0) {
			for (int i = 0; i < paramArray.size(); i++) {
				JSONObject jsonObj = paramArray.getJSONObject(i);
				MappingRule mappingRule = new MappingRule(i + "", jsonObj.getString("sourceParam"),
						TargetType.valueOf(jsonObj.getString("paramType").toUpperCase()),
						jsonObj.getString("targetKey"));
				rules.add(mappingRule);
			}
		}

		HttpHeaders headers = new HttpHeaders();
		// 2. 构建请求体（JSON 格式）
		Map<String, String> queryParams = new HashMap<>();
		Map<String, Object> bodyMap = new HashMap<>();

		for (MappingRule rule : rules) {
			Object value = getValueByPath(input, rule.sourcePath());

			switch (rule.targetType()) {
			case HEADER -> addHeader(headers,rule.targetKey(), value);
			case QUERY -> setQueryByPath(queryParams,rule.targetKey(), value);
			case BODY -> setValueByPath(bodyMap, rule.targetKey(), value);
			}
		}

		// 3. 封装请求实体（Header + Body）
		HttpEntity<String> requestEntity = new HttpEntity<>(JSON.toJSONString(bodyMap), headers);

		String queryString = queryParams.entrySet().stream()
				.map(entry -> URLEncoder.encode(entry.getKey(), StandardCharsets.UTF_8) + "="
						+ URLEncoder.encode(entry.getValue(), StandardCharsets.UTF_8))
				.collect(Collectors.joining("&"));
		String reqUrl = url + (queryString.isEmpty() ? "" : "?" + queryString);
		ResponseEntity<Object> response = null;
		if (HttpMethod.POST.name().equals(httpMethod)) {
			// 4. 发送 POST 请求
			response = restTemplate.postForEntity(reqUrl, requestEntity, Object.class);
		} else if (HttpMethod.GET.name().equals(httpMethod)) {
			response = restTemplate.exchange(reqUrl, // 请求地址
					HttpMethod.GET, // 请求方法
					requestEntity, // 包含 Header 的实体
					Object.class // 响应类型
			);
		}

		Map<String, Object> output = new HashMap<>(input);
		if (response != null) {
			mergeResult(output, resultKey, response.getBody());
		}

		return output;
	}

	private void mergeResult(Map<String, Object> output, String key, Object newValue) {
		if (output.containsKey(key)) {
			Object existingValue = output.get(key);

			if (existingValue instanceof List && newValue instanceof List) {
				List<Object> mergedList = new ArrayList<>((List<?>) existingValue);
				mergedList.addAll((List<?>) newValue);
				output.put(key, mergedList);
			} else if (existingValue instanceof Map && newValue instanceof Map) {
				Map<Object, Object> mergedMap = new HashMap<>((Map<?, ?>) existingValue);
				mergedMap.putAll((Map<?, ?>) newValue);
				output.put(key, mergedMap);
			} else {
				output.put(key, newValue);
			}
		} else {
			output.put(key, newValue);
		}
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
	private void setQueryByPath(Map<String, String> queryParams, String path, Object value) {
		if(value == null) {
			return;
		}
		queryParams.put(path, value.toString());
	}

	@SuppressWarnings("unchecked")
	private void setValueByPath(Map<String, Object> map, String path, Object value) {
		if(value == null) {
			return;
		}
		String[] keys = path.split("\\.");
		Map<String, Object> current = map;
		for (int i = 0; i < keys.length - 1; i++) {
			current = (Map<String, Object>) current.computeIfAbsent(keys[i], k -> new HashMap<String, Object>());
		}
		current.put(keys[keys.length - 1], value);
	}
	
	/**
     * 直接获取Request对象（简化版，需确保当前有请求上下文）
     * 无上下文时抛出NullPointerException，适合确定有请求的场景
     * @return HttpServletRequest
     */
    public static HttpServletRequest getRequestDirectly() {
        ServletRequestAttributes attributes = (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
        if (attributes == null) {
            return null;
        }
        return attributes.getRequest();
    }
    
    private void addHeader(HttpHeaders headers,String key, Object value) {
    	HttpServletRequest request = getRequestDirectly();
    	if(request == null&&value != null) {
    		headers.add(key, value.toString());
    	} else {
    		headers.add(key, request.getHeader(key));
    	}
    }

}
