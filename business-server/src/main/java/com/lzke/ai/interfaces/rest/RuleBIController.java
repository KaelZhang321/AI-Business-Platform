package com.lzke.ai.interfaces.rest;

import java.util.Map;

import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.lecz.service.tools.core.dto.ResponseDto;
import com.lzke.ai.application.rule.service.SQLRuleService;

import io.swagger.v3.oas.annotations.Operation;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;

/**
 * 
 * 客户bi统计相关接口
 * 
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/rule/")
public class RuleBIController {
	
	@Resource
	SQLRuleService sQLRuleService;
	
	/**
     * 根据ID查询订单
     */
    @Operation(summary = "云健康订单数据查询")
    @PostMapping("/{ruleCode}/{version}")
    public ResponseDto executeRule(@PathVariable("ruleCode") String ruleCode,@PathVariable("version") Integer version,@RequestBody Map<String, Object> params) {
    	try {
    		return ResponseDto.success(sQLRuleService.executeRule(ruleCode, version,params));
		} catch (Exception e) {
			log.error("ruleCode={},version={},执行失败",ruleCode,version,e);
			return ResponseDto.fail(e.getMessage());
		}
    }
    
}
