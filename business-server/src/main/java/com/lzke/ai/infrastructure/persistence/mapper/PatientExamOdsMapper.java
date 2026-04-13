package com.lzke.ai.infrastructure.persistence.mapper;

import com.baomidou.dynamic.datasource.annotation.DS;
import com.lzke.ai.application.exam.dto.PatientExamDepartmentTable;
import com.lzke.ai.application.exam.dto.PatientExamPatientInfoResponse;
import com.lzke.ai.application.exam.dto.PatientExamPatientQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamResultItemResponse;
import com.lzke.ai.application.exam.dto.PatientExamSessionQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamSessionRowResponse;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 患者体检结果 ODS 查询 Mapper。
 *
 * <p>该 Mapper 固定走 ODS 动态数据源，负责：
 *
 * <ul>
 *     <li>查询参与动态 UNION 的科室列表</li>
 *     <li>按选定科室拼接 `ods_tj_${ksbm}b` 结果表</li>
 *     <li>分页查询结果明细与总数</li>
 * </ul>
 */
@Mapper
@DS("odc")
public interface PatientExamOdsMapper {

    /**
     * 查询参与结果拼接的科室表定义。
     *
     * @param departmentCodes 前端传入的部门编码，可为空
     * @return 科室表列表
     */
    List<PatientExamDepartmentTable> selectDepartmentTables(@Param("departmentCodes") List<String> departmentCodes);

    /**
     * 查询指定动态表的实际列名。
     *
     * <p>ODS 按科室拆表后，不同科室表通常大体一致，但也可能存在字段增减。
     * 服务层会先读出真实列名，再为每张表构造安全的字段表达式，避免动态 SQL
     * 直接引用不存在的列导致整条查询失败。
     *
     * @param tableName 表名
     * @return 列名列表
     */
    List<String> selectTableColumns(@Param("tableName") String tableName);

    /**
     * 查询患者基础信息。
     *
     * <p>当前实现会按最近一次体检主记录返回，用于前端先展示患者卡片。
     */
    PatientExamPatientInfoResponse selectPatientInfo(@Param("request") PatientExamPatientQueryRequest request);

    /**
     * 查询符合条件的体检主记录总数。
     *
     * <p>这里以 {@code ods_tj_jcxx} 为主表分页，避免每条科室结果都重复携带患者信息。
     */
    long countPatientExamSessions(@Param("request") PatientExamSessionQueryRequest request);

    /**
     * 分页查询体检主记录。
     */
    List<PatientExamSessionRowResponse> selectPatientExamSessions(@Param("request") PatientExamSessionQueryRequest request);

    /**
     * 按体检主单号查询单次体检主记录。
     */
    PatientExamSessionRowResponse selectPatientExamSessionByStudyId(@Param("studyId") String studyId);

    /**
     * 批量按体检主单号查询体检主记录。
     */
    List<PatientExamSessionRowResponse> selectPatientExamSessionsByStudyIds(@Param("studyIds") List<String> studyIds);

    /**
     * 按身份证号查询该患者全部体检主记录。
     */
    List<PatientExamSessionRowResponse> selectPatientExamSessionsByIdCard(@Param("idCard") String idCard);

    /**
     * 查询当前页体检主记录下的科室结果明细。
     *
     * <p>这里仅按当前页 {@code studyId} 集合查动态科室表，再由服务层组装成
     * “体检 -> 科室 -> 细项”的层级结构。
     */
    List<PatientExamResultItemResponse> selectPatientExamDepartmentItems(
            @Param("studyIds") List<String> studyIds,
            @Param("tables") List<PatientExamDepartmentTable> tables
    );
}
