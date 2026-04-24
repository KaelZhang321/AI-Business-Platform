package com.lzke.ai.application.rule.service;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.google.common.base.Strings;
import com.lecz.service.tools.core.dto.ResponseDto;
import com.lzke.ai.application.rule.dao.RuleMapper;
import com.lzke.ai.application.rule.dao.RuleNodeMapper;
import com.lzke.ai.application.rule.dto.RuleQueryDTO;
import com.lzke.ai.application.rule.po.Rule;
import com.lzke.ai.application.rule.po.RuleNode;

import cn.hutool.core.util.IdUtil;
import lombok.extern.slf4j.Slf4j;

/**
 * 客户bi统计相关接口
 * 
 */
@Service
@Slf4j
public class RuleService extends ServiceImpl<RuleMapper, Rule> {

	@Autowired
	RuleNodeMapper ruleNodeMapper;

	/**
	 * 规则列表
	 * 
	 * @param ruleQueryDTO
	 * @return
	 */
	public ResponseDto<Page<Rule>> ruleList(RuleQueryDTO ruleQueryDTO) {

		LambdaQueryWrapper<Rule> lambdaRuleWrapper = new LambdaQueryWrapper<Rule>();
//		lambdaRuleWrapper.eq(Rule::getStatus, 1);
		lambdaRuleWrapper.orderByDesc(Rule::getUpdatedTime);
		Page<Rule> pageRule = this.page(ruleQueryDTO.build(), lambdaRuleWrapper);

		return ResponseDto.success(pageRule);
	}

	/**
	 * 规则详情
	 * 
	 * @param ruleQueryDTO
	 * @return
	 */
	public ResponseDto<Rule> getRuleById(Long id) {
		Rule rule = this.getById(id);

		LambdaQueryWrapper<RuleNode> lambdaRuleNodeWrapper = new LambdaQueryWrapper<RuleNode>();
		lambdaRuleNodeWrapper.eq(RuleNode::getRuleId, rule.getId());
		lambdaRuleNodeWrapper.eq(RuleNode::getRuleVersion, rule.getVersion()).orderByAsc(RuleNode::getSortOrder);
		List<RuleNode> ruleNodeList = ruleNodeMapper.selectList(lambdaRuleNodeWrapper);

		rule.setRuleNodes(ruleNodeList);
		return ResponseDto.success(rule);
	}

	/**
	 * 添加规则
	 * 
	 * @param ruleQueryDTO
	 * @return
	 */
	@Transactional
	public ResponseDto<Rule> saveOrUpdateRule(Rule rule) {
		if (rule.getId() == null) {
			Long id = IdUtil.getSnowflake().nextId();
			rule.setId(id);
			this.save(rule);

		} else {
			
			if("1".equals(rule.getStatus())) {
				return ResponseDto.fail("激活状态的规则不允许修改");
			}
			
			this.updateById(rule);
			// 先删除规则节点
			LambdaQueryWrapper<RuleNode> lambdaRuleNodeWrapper = new LambdaQueryWrapper<RuleNode>();
			lambdaRuleNodeWrapper.eq(RuleNode::getRuleId, rule.getId());
			lambdaRuleNodeWrapper.eq(RuleNode::getRuleVersion, rule.getVersion());
			ruleNodeMapper.delete(lambdaRuleNodeWrapper);
			// 重新生成规则节点
			generateNode(rule);
//			Rule newRule = this.getById(rule.getId());
//			if (Strings.isNullOrEmpty(newRule.getNodeDetail())) {
//				this.updateById(rule);
//				if (!Strings.isNullOrEmpty(rule.getNodeDetail())) {
//					generateNode(rule);
//				}
//			} else {
//				Long id = IdUtil.getSnowflake().nextId();
//				// 规则有变更，新增一条规则记录，版本号+1
//				rule.setId(id);
//				rule.setVersion(id+"");
//				this.save(rule);
//				if (!Strings.isNullOrEmpty(rule.getNodeDetail())) {
//					generateNode(rule);
//				}
//			}
		}
		return ResponseDto.success();
	}

	private void generateNode(Rule rule) {
		JSONObject nodeDetailObj = JSON.parseObject(rule.getNodeDetail());
		JSONArray jsonArray = nodeDetailObj.getJSONArray("nodes");
		if (jsonArray != null && !jsonArray.isEmpty()) {
			for (int i = 0; i < jsonArray.size(); i++) {
				JSONObject nodeJson = jsonArray.getJSONObject(i);
				JSONObject nodeDataJson = nodeJson.getJSONObject("data");
				if (nodeDataJson != null) {
					JSONObject paramsDataJson = nodeDataJson.getJSONObject("params");
					if (paramsDataJson != null) {
						Long id = IdUtil.getSnowflake().nextId();
						RuleNode ruleNode = new RuleNode();
						String nodeTyle = paramsDataJson.getString("nodeType");
						ruleNode.setNodeName(paramsDataJson.getString("label"));
						ruleNode.setNodeType(nodeTyle);
						ruleNode.setId(id);
						ruleNode.setRuleId(rule.getId());
						ruleNode.setRuleVersion(rule.getVersion());
						ruleNode.setNodeGroup(paramsDataJson.getString("nodeGroup"));

						JSONObject nodeConfigJson = paramsDataJson.getJSONObject("nodeConfig");
						if (nodeConfigJson != null) {
							ruleNode.setNodeConfig(nodeConfigJson.toJSONString());
						}
						ruleNode.setNodeSql(paramsDataJson.getString("nodeSql"));
						ruleNode.setSortOrder(i + 1);
						ruleNodeMapper.insert(ruleNode);
					}

				}
			}

		}
	}

	@SuppressWarnings("rawtypes")
	public ResponseDto delete(Long id) {
		Rule rule = this.getById(id);
		if("1".equals(rule.getStatus())) {
			return ResponseDto.fail("激活状态的规则不允许修改");
		}
		this.removeById(id);
		LambdaQueryWrapper<RuleNode> lambdaRuleNodeWrapper = new LambdaQueryWrapper<RuleNode>();
		lambdaRuleNodeWrapper.eq(RuleNode::getRuleId, rule.getId());
		lambdaRuleNodeWrapper.eq(RuleNode::getRuleVersion, rule.getVersion());
		ruleNodeMapper.delete(lambdaRuleNodeWrapper);
		
		return ResponseDto.success();
	}
	
	public ResponseDto<Rule> enable(Long id) {
		Rule rule = this.getById(id);
		if("1".equals(rule.getStatus())) {
			rule.setStatus("0");
		} else {
			rule.setStatus("1");
		}
		this.updateById(rule);
		return this.getRuleById(id);
	}

}
