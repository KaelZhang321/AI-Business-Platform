package com.lzke.ai.interfaces.rest;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.lecz.service.tools.core.dto.ResponseDto;
import com.lzke.ai.application.rule.dto.RuleDataSourceResponse;
import com.lzke.ai.application.rule.dto.RuleQueryDTO;
import com.lzke.ai.application.rule.po.Rule;
import com.lzke.ai.application.rule.service.RuleService;
import com.lzke.ai.application.rule.service.SQLRuleService;

import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;

/**
 * 
 * 客户bi统计相关接口
 * 
 */
@RestController
@RequestMapping("/api/v1/rule")
public class RuleController {
	
	@Resource
	RuleService ruleService;

	@Resource
	SQLRuleService sqlRuleService;
    
    @Operation(summary = "规则列表查询")
    @PostMapping("/ruleList")
    public ResponseDto ruleList(@RequestBody RuleQueryDTO ruleQueryDTO) {
    	return ruleService.ruleList(ruleQueryDTO);
    }
    
    @Operation(summary = "规则详情")
    @GetMapping("/getRuleById/{id}")
    public ResponseDto<Rule> getRuleById(@PathVariable("id") Long id) {
    	return ruleService.getRuleById(id);
    }

    @Operation(summary = "规则引擎可选数据源列表")
    @GetMapping("/data-sources")
    public ResponseDto<java.util.List<RuleDataSourceResponse>> listDataSources() {
    	return ResponseDto.success(sqlRuleService.listDataSources());
    }
    
    /**
     * 
     * @param id
     * @return
     */
    @Operation(summary = "规则详情")
    @PostMapping("/saveOrUpdateRule")
    public ResponseDto<Rule> saveOrUpdateRule(@RequestBody Rule rule) {
    	return ruleService.saveOrUpdateRule(rule);
    }
    
    /**
     * 
     * @param id
     * @return
     */
    @Operation(summary = "规则详情")
    @DeleteMapping("/delete/{id}")
    public ResponseDto delete(@PathVariable("id") Long id) {
    	return ruleService.delete(id);
    }
    
    /**
     * 
     * @param id
     * @return
     */
    @Operation(summary = "启用禁用")
    @GetMapping("/enable/{id}")
    public ResponseDto enable(@PathVariable("id") Long id) {
    	return ruleService.enable(id);
    }

}
