package com.lzke.ai.application.exam.dto;

import com.lzke.ai.application.dto.PageQuery;
import lombok.Data;

import java.util.List;

/**
 * 患者体检结果动态查询请求。
 *
 * <p>该请求用于面向 ODS 体检库做跨科室结果查询，支持：
 *
 * <ul>
 *     <li>按患者维度信息筛选</li>
 *     <li>部门不传时查询全部科室</li>
 *     <li>部门多选时仅查询指定科室</li>
 *     <li>按时间倒序分页返回</li>
 * </ul>
 *
 * <p>由于不同体检机构的 ODS 字段命名可能存在差异，这里保留一组相对通用的患者筛选条件；
 * 运行时真正命中的列名在 Mapper XML 中按当前库结构映射。
 */
@Data
public class PatientExamQueryRequest extends PageQuery {

    /**
     * 体检单号 / 订单号。
     */
    private String orderCode;

    /**
     * 患者姓名。
     */
    private String patientName;

    /**
     * 身份证号。
     */
    private String idCard;

    /**
     * 手机号。
     */
    private String mobile;

    /**
     * 会员号 / 病历号 / 客户编码等院内主索引。
     */
    private String patientNo;

    /**
     * 前端传入的科室编码列表，例如：["HY","US"]。
     *
     * <p>不传或为空时默认查询全部科室。
     */
    private List<String> departmentCodes;

    /**
     * 体检开始时间，字符串形式透传到 SQL。
     *
     * <p>建议前端按 yyyy-MM-dd HH:mm:ss 传入。
     */
    private String startTime;

    /**
     * 体检结束时间，字符串形式透传到 SQL。
     *
     * <p>建议前端按 yyyy-MM-dd HH:mm:ss 传入。
     */
    private String endTime;
}
