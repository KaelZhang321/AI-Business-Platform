package com.lzke.ai.application.rule.service;

import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;

import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.google.common.collect.Lists;
import com.lzke.ai.application.rule.AggregateNode;
import com.lzke.ai.application.rule.CalculateNode;
import com.lzke.ai.application.rule.HttpRequestNode;
import com.lzke.ai.application.rule.InputNode;
import com.lzke.ai.application.rule.ParseResultNode;
import com.lzke.ai.application.rule.RuleEngine;
import com.lzke.ai.application.rule.SqlExecuteNode;
import com.lzke.ai.application.rule.InputNode.ValidationRule;
import com.lzke.ai.application.rule.InputNode.ValidationType;
import com.lzke.ai.application.rule.SqlExecuteNode.ResultType;
import com.lzke.ai.application.rule.constants.RuleConstants;
import com.lzke.ai.application.rule.dao.RuleMapper;
import com.lzke.ai.application.rule.dao.RuleNodeMapper;
import com.lzke.ai.application.rule.po.Rule;
import com.lzke.ai.application.rule.po.RuleNode;

import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;

/**
 * 客户bi统计相关接口
 * 
 */
@Service
@Slf4j
public class SQLRuleService {

	@Autowired
	RuleMapper ruleMapper;

	@Autowired
	RuleNodeMapper ruleNodeMapper;

	@Autowired
	@Qualifier("odcJdbcTemplate")
	JdbcTemplate odcJdbcTemplate;
	
	@Resource
	private ExecutorService executorService;
	
	@Resource
	private RestTemplate restTemplate;

	/**
	 * 执行规则引擎
	 * 
	 * @param ruleCode 规则编码
	 * @param version  规则版本号
	 * @param params   输入参数
	 * @return 规则执行结果
	 */
	public Map<String, Object> executeRule(String ruleCode, Integer version, Map<String, Object> params) throws Exception{

		// 1. 查询规则基本信息（根据规则编码、版本号、激活状态）
		LambdaQueryWrapper<Rule> lambdaRuleWrapper = new LambdaQueryWrapper<Rule>();
		lambdaRuleWrapper.eq(Rule::getRuleCode, ruleCode);
		lambdaRuleWrapper.eq(Rule::getVersion, version);
		lambdaRuleWrapper.eq(Rule::getStatus, RuleConstants.RuleStatus.ACTIVE);

		Rule rule = ruleMapper.selectOne(lambdaRuleWrapper);
		if (rule == null) {
			log.warn("规则不存在或未激活，ruleCode: {}, version: {}", ruleCode, version);
			return Collections.emptyMap();
		}

		// 2. 查询规则的所有节点（按sortOrder排序保证执行顺序）
		LambdaQueryWrapper<RuleNode> lambdaRuleNodeWrapper = new LambdaQueryWrapper<RuleNode>();
		lambdaRuleNodeWrapper.eq(RuleNode::getRuleId, rule.getId());
		lambdaRuleNodeWrapper.eq(RuleNode::getRuleVersion, rule.getVersion())
		.orderByAsc(RuleNode::getSortOrder);
		List<RuleNode> ruleNodeList = ruleNodeMapper.selectList(lambdaRuleNodeWrapper);

		if (ruleNodeList == null || ruleNodeList.isEmpty()) {
			log.warn("规则节点为空，ruleId: {}", rule.getId());
			return Collections.emptyMap();
		}

		// 3. 创建规则引擎实例
		RuleEngine engine = null;
		if(params.containsKey("useParallel") && (Boolean)params.get("useParallel") == true) {
			params.remove("useParallel");
			engine = new RuleEngine(rule.getRuleName(),executorService);
		} else {
			engine = new RuleEngine(rule.getRuleName());
		}

		// 4. 遍历节点，根据nodeType和nodeConfig动态构建节点
		for (RuleNode node : ruleNodeList) {
			String nodeType = node.getNodeType();
			String nodeConfig = node.getNodeConfig();

			// 4.1 输入节点：直接传入用户参数
			// nodeConfig格式：空或{}
			if (RuleConstants.NodeType.INPUT_NODE.equals(nodeType)) {
				JSONObject config = JSON.parseObject(nodeConfig);
				JSONArray jsonArray = config.getJSONArray("validationRules");
				if(jsonArray != null&&jsonArray.size() > 0) {
					List<ValidationRule> validationRules = Lists.newArrayList();
					
					for (int i = 0; i < jsonArray.size(); i++) {
						JSONObject jsonObj = jsonArray.getJSONObject(i);
						String vaule = jsonObj.getString("value");
						if(!StringUtils.isEmpty(vaule)) {
							ValidationRule v = new ValidationRule(jsonObj.getString("paramName"),ValidationType.valueOf(jsonObj.getString("type")),jsonObj.getString("value"));
							validationRules.add(v);
						} else {
							ValidationRule v = new ValidationRule(jsonObj.getString("paramName"),ValidationType.valueOf(jsonObj.getString("type")));
							validationRules.add(v);
						}
					}
					engine.addNode(new InputNode(node.getNodeName(), params,validationRules));
					
				} else {
					engine.addNode(new InputNode(node.getNodeName(), params));
				}
				
			// 4.2 SQL执行节点：根据配置执行SQL查询
			// nodeConfig格式：
			// {
			//   "sqlTemplate": "SELECT * FROM user WHERE id = ${userId}",
			//   "resultKey": "userResult"
			// }
			// SQL模板支持的占位符语法：
			// - ${参数名} - 等于查询，例如：WHERE id = ${userId}
			// - ${参数名:>=} - 大于等于，例如：WHERE age ${minAge:>=}
			// - ${参数名:>} - 大于
			// - ${参数名:<} - 小于
			// - ${参数名:<=} - 小于等于
			// - ${参数名:!=} - 不等于
			// - ${参数名:LIKE} - 模糊查询（%value%）
			// - ${参数名:LIKE_LEFT} - 左模糊（%value）
			// - ${参数名:LIKE_RIGHT} - 右模糊（value%）
			// - IN (${参数名}) - IN查询，参数需为List或数组
			} else if (RuleConstants.NodeType.SQL_EXECUTE_NODE.equals(nodeType)) {
				JSONObject config = JSON.parseObject(nodeConfig);
				String resultKey = config.getString("resultKey");
				String resultType = config.getString("resultType");
				if(resultType == null || resultType.isEmpty()) {
					resultType = "TO_MAP_LIST";
					
				}
				
				engine.addNode(
						new SqlExecuteNode(node.getNodeName(), odcJdbcTemplate, node.getNodeSql(), resultKey,ResultType.valueOf(resultType)));

			// 4.3 结果解析节点：解析SQL查询结果
			// nodeConfig格式：
			// {
			//   "sourceKey": "userResult",           // 源数据key
			//   "targetKey": "userIds",              // 目标数据key
			//   "parseType": "TO_STRING_ARRAY",      // 解析类型：TO_LIST/TO_STRING_ARRAY/EXTRACT_COLUMN/TO_MAP_LIST
			//   "columnName": "user_id",             // 提取的列名（当parseType为TO_STRING_ARRAY或EXTRACT_COLUMN时必填）
			//   "filterCondition": {                 // 可选：过滤条件
			//     "columnName": "age",               // 过滤字段
			//     "operator": "GREATER_THAN",        // 过滤运算符：EQUALS/NOT_EQUALS/GREATER_THAN/GREATER_THAN_OR_EQUAL/LESS_THAN/LESS_THAN_OR_EQUAL/LIKE/IN/NOT_IN
			//     "value": 18                        // 过滤值
			//   }
			// }
			} else if (RuleConstants.NodeType.PARSE_RESULT_NODE.equals(nodeType)) {
				JSONObject config = JSON.parseObject(nodeConfig);
				String sourceKey = config.getString("sourceKey");
				String targetKey = config.getString("targetKey");
				String parseType = config.getString("parseType");
				String columnName = config.getString("columnName");

				ParseResultNode.ParseType type = ParseResultNode.ParseType.valueOf(parseType);

				// 检查是否有过滤条件
				if (config.containsKey("filterCondition")) {
					JSONObject filterConfig = config.getJSONObject("filterCondition");
					String filterColumn = filterConfig.getString("columnName");
					String filterOperator = filterConfig.getString("operator");
					Object filterValue = filterConfig.get("value");

					ParseResultNode.FilterOperator operator = ParseResultNode.FilterOperator
							.valueOf(filterOperator);
					ParseResultNode.FilterCondition filterCondition = new ParseResultNode.FilterCondition(
							filterColumn, operator, filterValue);

					engine.addNode(new ParseResultNode(node.getNodeName(), sourceKey, targetKey, type, columnName,
							filterCondition));
				} else {
					engine.addNode(new ParseResultNode(node.getNodeName(), sourceKey, targetKey, type, columnName));
				}

			// 4.4 聚合节点：聚合多个节点的输出结果
			// nodeConfig格式1（重命名）：
			// {
			//   "keyMapping": {
			//     "userResult": "users",    // key重命名映射
			//     "orderResult": "orders"
			//   }
			// }
			// nodeConfig格式2（选择字段）：
			// {
			//   "includeKeys": ["userResult", "orderResult"]  // 包含的key列表
			// }
			} else if (RuleConstants.NodeType.AGGREGATE_NODE.equals(nodeType)) {
				JSONObject config = JSON.parseObject(nodeConfig);

				if (config.containsKey("keyMapping")) {
					Map<String, String> keyMapping = config.getObject("keyMapping", Map.class);
					engine.addNode(new AggregateNode(node.getNodeName(), keyMapping));
				} else if (config.containsKey("includeKeys")) {
					List<String> includeKeys = config.getJSONArray("includeKeys").toJavaList(String.class);
					engine.addNode(new AggregateNode(node.getNodeName(), includeKeys));
				}
				
				// 4.5 计算节点：执行数学运算
				// nodeConfig格式：
				// {
				//   "expression": "${price} * ${quantity} - ${discount}",  // 计算表达式，支持+、-、*、/
				//   "resultKey": "totalAmount",                            // 结果存储的key
				//   "scale": 2,                                            // 小数精度（可选，默认2）
				//   "roundingMode": "HALF_UP"                              // 舍入模式（可选，默认HALF_UP）
				// }
				// 支持的取值方式：
				// - ${key} - 从上下文直接取值
				// - ${key.field} - 从Map中取字段值
				// - ${key.0.field} - 从List中取索引值再取字段
				// 示例表达式：
				// - "${price} * ${quantity}"
				// - "(${price} + ${tax}) * ${quantity}"
				// - "${orderList.0.amount} + ${orderList.1.amount}"
			} else if (RuleConstants.NodeType.CALCULATE_NODE.equals(nodeType)) {
				JSONObject config = JSON.parseObject(nodeConfig);
				String expression = config.getString("expression");
				String calcResultKey = config.getString("resultKey");
				Integer scale = config.getInteger("scale");
				String roundingMode = config.getString("roundingMode");

				if (scale != null && roundingMode != null) {
					engine.addNode(new CalculateNode(
							node.getNodeName(),
							expression,
							calcResultKey,
							scale,
							java.math.RoundingMode.valueOf(roundingMode)
					));
				} else {
					engine.addNode(new CalculateNode(node.getNodeName(), expression, calcResultKey));
				}
			} else if (RuleConstants.NodeType.HTTP_REQUEST_NODE.equals(nodeType)) {
				engine.addNode(new HttpRequestNode(node.getNodeName(), restTemplate, nodeConfig));
			}
		}

		// 5. 执行规则引擎并返回结果
		Map<String, Object> result = engine.execute(new HashMap<>());
		log.info("规则执行成功，ruleCode: {}, version: {}", ruleCode, version);
		return result;

	}

}
