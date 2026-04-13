package com.lzke.ai.application.exam;

import com.lzke.ai.application.exam.dto.PatientExamBatchResultQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamDepartmentResponse;
import com.lzke.ai.application.exam.dto.PatientExamDepartmentResultResponse;
import com.lzke.ai.application.exam.dto.PatientExamDepartmentTable;
import com.lzke.ai.application.exam.dto.PatientExamItemResultResponse;
import com.lzke.ai.application.exam.dto.PatientExamPatientInfoResponse;
import com.lzke.ai.application.exam.dto.PatientExamPatientQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamResultItemResponse;
import com.lzke.ai.application.exam.dto.PatientExamResultQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamSessionQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamSessionResponse;
import com.lzke.ai.application.exam.dto.PatientExamSessionRowResponse;
import com.lzke.ai.application.exam.dto.PatientExamSessionSummaryResponse;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import com.lzke.ai.infrastructure.persistence.mapper.PatientExamOdsMapper;
import com.lzke.ai.interfaces.dto.PageResult;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * 患者体检查询应用服务。
 *
 * <p>当前按前端页面拆成三条链路：
 *
 * <ul>
 *     <li>先根据患者条件查询基础信息</li>
 *     <li>再分页查询该患者有多少次体检</li>
 *     <li>最后按某次体检和可选科室查询科室结果明细</li>
 * </ul>
 *
 * <p>动态科室结果表仍然按 {@code ods_tj_${ksbm小写}b} 解析，并在查询前先探测真实列名，
 * 避免不同科室表字段差异导致整条 SQL 失败。
 */
@Service
@RequiredArgsConstructor
public class PatientExamApplicationService {

    private static final Pattern DEPARTMENT_CODE_PATTERN = Pattern.compile("^[A-Za-z0-9_]+$");
    private static final int MAX_BATCH_REPORTS = 10;

    private final PatientExamOdsMapper patientExamOdsMapper;

    /**
     * 查询可选科室列表。
     */
    public List<PatientExamDepartmentResponse> listDepartments() {
        return patientExamOdsMapper.selectDepartmentTables(null).stream()
                .map(table -> new PatientExamDepartmentResponse(table.getDepartmentCode(), table.getDepartmentName()))
                .toList();
    }

    /**
     * 查询患者基础信息。
     *
     * <p>当前实现按最近一次体检主记录返回一份患者信息，适合前端先展示患者头信息。
     */
    public PatientExamPatientInfoResponse getPatientInfo(PatientExamPatientQueryRequest request) {
        validatePatientFilters(request);
        return patientExamOdsMapper.selectPatientInfo(request);
    }

    /**
     * 分页查询患者体检记录。
     *
     * <p>这里以 {@code ods_tj_jcxx} 主表分页，前端可据此看到患者一共有多少次体检，
     * 再决定点哪一次进详情。
     */
    public PageResult<PatientExamSessionSummaryResponse> listExamSessions(PatientExamSessionQueryRequest request) {
        validatePatientFilters(
                request.getOrderCode(),
                request.getPatientName(),
                request.getIdCard(),
                request.getMobile(),
                request.getPatientNo()
        );

        long total = patientExamOdsMapper.countPatientExamSessions(request);
        if (total <= 0) {
            return PageResult.empty(request.getPage(), request.getSize());
        }

        List<PatientExamSessionSummaryResponse> data = patientExamOdsMapper.selectPatientExamSessions(request).stream()
                .map(this::toSessionSummary)
                .toList();
        return PageResult.of(data, total, request.getPage(), request.getSize());
    }

    /**
     * 查询某次体检的结果信息。
     *
     * <p>前端可传单个 {@code studyId}，并可选传科室编码列表做过滤；
     * 不传科室时默认查询该次体检的全部科室结果。
     */
    public PatientExamSessionResponse getExamResult(PatientExamResultQueryRequest request) {
        validateExamResultRequest(request);

        PatientExamSessionRowResponse sessionRow = patientExamOdsMapper.selectPatientExamSessionByStudyId(request.getStudyId());
        if (sessionRow == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到对应体检记录: " + request.getStudyId());
        }

        List<String> normalizedDepartmentCodes = normalizeDepartmentCodes(request.getDepartmentCodes());
        List<PatientExamDepartmentTable> tables = patientExamOdsMapper.selectDepartmentTables(normalizedDepartmentCodes);
        if (tables.isEmpty()) {
            return buildSession(sessionRow, Collections.emptyList());
        }

        List<PatientExamDepartmentTable> resolvedTables = resolveTables(tables);
        if (resolvedTables.isEmpty()) {
            return buildSession(sessionRow, Collections.emptyList());
        }

        List<PatientExamResultItemResponse> detailRows = patientExamOdsMapper.selectPatientExamDepartmentItems(
                Collections.singletonList(request.getStudyId()),
                resolvedTables
        );
        return buildSession(sessionRow, detailRows);
    }

    /**
     * 批量查询多次体检结果。
     *
     * <p>前端通常会先从体检记录列表勾选若干次体检做对比，所以这里支持按 studyId 批量拉取；
     * 为了控制动态科室分表的查询规模，单次最多支持 10 份体检报告。
     */
    public List<PatientExamSessionResponse> getBatchExamResults(PatientExamBatchResultQueryRequest request) {
        validateBatchExamResultRequest(request);

        String normalizedIdCard = StringUtils.trimWhitespace(request.getIdCard());
        List<PatientExamSessionRowResponse> sessionRows;
        if (StringUtils.hasText(normalizedIdCard)) {
            sessionRows = patientExamOdsMapper.selectPatientExamSessionsByIdCard(normalizedIdCard);
        } else {
            List<String> normalizedStudyIds = request.getStudyIds().stream()
                    .filter(StringUtils::hasText)
                    .map(String::trim)
                    .distinct()
                    .toList();
            sessionRows = patientExamOdsMapper.selectPatientExamSessionsByStudyIds(normalizedStudyIds);
        }

        if (sessionRows.isEmpty()) {
            return Collections.emptyList();
        }

        List<String> normalizedDepartmentCodes = normalizeDepartmentCodes(request.getDepartmentCodes());
        List<PatientExamDepartmentTable> tables = patientExamOdsMapper.selectDepartmentTables(normalizedDepartmentCodes);
        if (tables.isEmpty()) {
            return sessionRows.stream()
                    .map(row -> buildSession(row, Collections.emptyList()))
                    .toList();
        }

        List<PatientExamDepartmentTable> resolvedTables = resolveTables(tables);
        if (resolvedTables.isEmpty()) {
            return sessionRows.stream()
                    .map(row -> buildSession(row, Collections.emptyList()))
                    .toList();
        }

        List<PatientExamResultItemResponse> detailRows = patientExamOdsMapper.selectPatientExamDepartmentItems(
                sessionRows.stream().map(PatientExamSessionRowResponse::getStudyId).distinct().toList(),
                resolvedTables
        );
        Map<String, List<PatientExamResultItemResponse>> detailByStudyId = detailRows.stream()
                .filter(row -> StringUtils.hasText(row.getStudyId()))
                .collect(Collectors.groupingBy(PatientExamResultItemResponse::getStudyId, LinkedHashMap::new, Collectors.toList()));

        return sessionRows.stream()
                .map(row -> buildSession(row, detailByStudyId.getOrDefault(row.getStudyId(), Collections.emptyList())))
                .toList();
    }

    /**
     * 校验患者筛选条件。
     */
    private void validatePatientFilters(PatientExamPatientQueryRequest request) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "体检查询请求不能为空");
        }
        validatePatientFilters(
                request.getOrderCode(),
                request.getPatientName(),
                request.getIdCard(),
                request.getMobile(),
                request.getPatientNo()
        );
    }

    private void validatePatientFilters(
            String orderCode,
            String patientName,
            String idCard,
            String mobile,
            String patientNo
    ) {
        if (!StringUtils.hasText(orderCode)
                && !StringUtils.hasText(patientName)
                && !StringUtils.hasText(idCard)
                && !StringUtils.hasText(mobile)
                && !StringUtils.hasText(patientNo)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "至少传入一项患者筛选条件");
        }
    }

    /**
     * 校验单次体检结果查询条件。
     */
    private void validateExamResultRequest(PatientExamResultQueryRequest request) {
        if (request == null || !StringUtils.hasText(request.getStudyId())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "studyId不能为空");
        }
    }

    /**
     * 校验批量体检结果查询条件。
     */
    private void validateBatchExamResultRequest(PatientExamBatchResultQueryRequest request) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "批量体检查询请求不能为空");
        }
        String normalizedIdCard = StringUtils.trimWhitespace(request.getIdCard());
        if (StringUtils.hasText(normalizedIdCard)) {
            return;
        }

        if (request.getStudyIds() == null || request.getStudyIds().isEmpty()) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "studyIds不能为空");
        }
        long count = request.getStudyIds().stream()
                .filter(StringUtils::hasText)
                .map(String::trim)
                .distinct()
                .count();
        if (count <= 0) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "studyIds不能为空");
        }
        if (count > MAX_BATCH_REPORTS) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "批量查询最多支持10份体检报告");
        }
    }

    /**
     * 规范化部门编码。
     */
    private List<String> normalizeDepartmentCodes(List<String> departmentCodes) {
        if (departmentCodes == null || departmentCodes.isEmpty()) {
            return null;
        }

        Set<String> uniqueCodes = new LinkedHashSet<>();
        for (String rawCode : departmentCodes) {
            if (!StringUtils.hasText(rawCode)) {
                continue;
            }
            String code = rawCode.trim().toUpperCase(Locale.ROOT);
            if (!DEPARTMENT_CODE_PATTERN.matcher(code).matches()) {
                throw new BusinessException(ErrorCode.BAD_REQUEST, "科室编码不合法: " + rawCode);
            }
            uniqueCodes.add(code);
        }
        return uniqueCodes.isEmpty() ? null : new ArrayList<>(uniqueCodes);
    }

    /**
     * 为每张科室结果表补全安全表名和字段表达式。
     */
    private List<PatientExamDepartmentTable> resolveTables(List<PatientExamDepartmentTable> tables) {
        List<PatientExamDepartmentTable> resolvedTables = new ArrayList<>();
        for (PatientExamDepartmentTable table : tables) {
            String departmentCode = table.getDepartmentCode();
            if (!StringUtils.hasText(departmentCode) || !DEPARTMENT_CODE_PATTERN.matcher(departmentCode).matches()) {
                continue;
            }

            String tableName = "ods_tj_" + departmentCode.toLowerCase(Locale.ROOT) + "b";
            List<String> columns = patientExamOdsMapper.selectTableColumns(tableName);
            if (columns == null || columns.isEmpty()) {
                continue;
            }

            Map<String, String> columnLookup = columns.stream()
                    .collect(Collectors.toMap(column -> column.toUpperCase(Locale.ROOT), column -> column, (left, right) -> left));

            PatientExamDepartmentTable resolved = new PatientExamDepartmentTable();
            resolved.setDepartmentCode(departmentCode);
            resolved.setDepartmentName(table.getDepartmentName());
            resolved.setTableName(tableName);
            resolved.setOrderCodeExpr(resolveSimpleExpr(columnLookup, "OrderCode"));
            resolved.setMajorItemCodeExpr(resolveSimpleExpr(columnLookup, "SFXMDM"));
            resolved.setItemCodeExpr(resolveItemCodeExpr(columnLookup));
            resolved.setItemNameExpr(null);
            resolved.setItemNameEnExpr(null);
            resolved.setResultValueExpr(resolveResultValueExpr(columnLookup));
            resolved.setUnitExpr(resolveUnitExpr(columnLookup));
            resolved.setReferenceRangeExpr(resolveReferenceRangeExpr(columnLookup));
            resolved.setAbnormalFlagExpr(resolveAbnormalFlagExpr(columnLookup));
            resolved.setExamTimeExpr(resolveExamTimeExpr(columnLookup));

            if (!StringUtils.hasText(resolved.getItemCodeExpr())
                    || !StringUtils.hasText(resolved.getResultValueExpr())) {
                continue;
            }

            resolvedTables.add(resolved);
        }
        return resolvedTables;
    }

    private String resolveSimpleExpr(Map<String, String> columnLookup, String columnName) {
        String actual = columnLookup.get(columnName.toUpperCase(Locale.ROOT));
        if (StringUtils.hasText(actual)) {
            return "t.`" + actual + "`";
        }
        return null;
    }

    private String resolveItemCodeExpr(Map<String, String> columnLookup) {
        String xxdmExpr = resolveSimpleExpr(columnLookup, "XXDM");
        if (StringUtils.hasText(xxdmExpr)) {
            return xxdmExpr;
        }
        return resolveSimpleExpr(columnLookup, "SFXMDM");
    }

    private String resolveResultValueExpr(Map<String, String> columnLookup) {
        String itemResultExpr = resolveSimpleExpr(columnLookup, "ItemResult");
        if (StringUtils.hasText(itemResultExpr)) {
            return itemResultExpr;
        }

        List<String> valueExprs = new ArrayList<>();
        addIfPresent(valueExprs, normalizeStringExpr(resolveSimpleExpr(columnLookup, "CValue")));
        addIfPresent(valueExprs, normalizeStringExpr(resolveSimpleExpr(columnLookup, "NValue")));

        String dateValueExpr = resolveSimpleExpr(columnLookup, "DValue");
        if (StringUtils.hasText(dateValueExpr)) {
            valueExprs.add("date_format(" + dateValueExpr + ", '%Y-%m-%d %H:%i:%s')");
        }

        addIfPresent(valueExprs, normalizeStringExpr(resolveSimpleExpr(columnLookup, "MValue")));

        if (valueExprs.isEmpty()) {
            return null;
        }
        return "coalesce(" + String.join(", ", valueExprs) + ")";
    }

    private String resolveUnitExpr(Map<String, String> columnLookup) {
        String itemUnitExpr = resolveSimpleExpr(columnLookup, "ItemUnit");
        if (StringUtils.hasText(itemUnitExpr)) {
            return itemUnitExpr;
        }
        return null;
    }

    private String resolveReferenceRangeExpr(Map<String, String> columnLookup) {
        String defValueExpr = resolveSimpleExpr(columnLookup, "DefValue");
        if (StringUtils.hasText(defValueExpr)) {
            return defValueExpr;
        }
        return null;
    }

    private String resolveAbnormalFlagExpr(Map<String, String> columnLookup) {
        String flagExpr = resolveSimpleExpr(columnLookup, "Flag");
        if (StringUtils.hasText(flagExpr)) {
            return "cast(" + flagExpr + " as char)";
        }
        return null;
    }

    private String resolveExamTimeExpr(Map<String, String> columnLookup) {
        String checkDateExpr = resolveSimpleExpr(columnLookup, "CheckDate");
        String checkTimeExpr = resolveSimpleExpr(columnLookup, "CheckTime");
        if (StringUtils.hasText(checkDateExpr)) {
            if (StringUtils.hasText(checkTimeExpr)) {
                return "str_to_date(concat(date_format(" + checkDateExpr + ", '%Y-%m-%d'), ' ', ifnull(" + checkTimeExpr + ", '00:00:00')), '%Y-%m-%d %H:%i:%s')";
            }
            return checkDateExpr;
        }

        String studyDateExpr = resolveSimpleExpr(columnLookup, "StudyDate");
        if (StringUtils.hasText(studyDateExpr)) {
            return studyDateExpr;
        }

        return resolveSimpleExpr(columnLookup, "UpDateTime");
    }

    private String normalizeStringExpr(String expr) {
        if (!StringUtils.hasText(expr)) {
            return null;
        }
        return "nullif(cast(" + expr + " as char), '')";
    }

    private void addIfPresent(List<String> exprs, String expr) {
        if (StringUtils.hasText(expr)) {
            exprs.add(expr);
        }
    }

    /**
     * 转体检摘要。
     */
    private PatientExamSessionSummaryResponse toSessionSummary(PatientExamSessionRowResponse row) {
        PatientExamSessionSummaryResponse response = new PatientExamSessionSummaryResponse();
        response.setStudyId(row.getStudyId());
        response.setOrderCode(row.getOrderCode());
        response.setExamTime(row.getExamTime());
        response.setPackageCode(row.getPackageCode());
        response.setPackageName(row.getPackageName());
        response.setAbnormalSummary(row.getAbnormalSummary());
        response.setFinalConclusion(row.getFinalConclusion());
        return response;
    }

    /**
     * 按 “体检 -> 科室 -> 细项” 聚合单次体检结果。
     */
    private PatientExamSessionResponse buildSession(
            PatientExamSessionRowResponse sessionRow,
            List<PatientExamResultItemResponse> detailRows
    ) {
        Map<String, PatientExamDepartmentResultResponse> departmentMap = new LinkedHashMap<>();
        for (PatientExamResultItemResponse detailRow : detailRows) {
            String departmentKey = detailRow.getDepartmentCode() + "::" + detailRow.getSourceTable();
            PatientExamDepartmentResultResponse department = departmentMap.computeIfAbsent(departmentKey, key -> {
                PatientExamDepartmentResultResponse response = new PatientExamDepartmentResultResponse();
                response.setDepartmentCode(detailRow.getDepartmentCode());
                response.setDepartmentName(detailRow.getDepartmentName());
                response.setSourceTable(detailRow.getSourceTable());
                response.setItems(new ArrayList<>());
                return response;
            });

            PatientExamItemResultResponse item = new PatientExamItemResultResponse();
            item.setMajorItemCode(detailRow.getMajorItemCode());
            item.setMajorItemName(detailRow.getMajorItemName());
            item.setItemCode(detailRow.getItemCode());
            item.setItemName(detailRow.getItemName());
            item.setItemNameEn(detailRow.getItemNameEn());
            item.setResultValue(detailRow.getResultValue());
            item.setUnit(detailRow.getUnit());
            item.setReferenceRange(detailRow.getReferenceRange());
            item.setAbnormalFlag(detailRow.getAbnormalFlag());
            department.getItems().add(item);
        }

        PatientExamSessionResponse response = new PatientExamSessionResponse();
        response.setStudyId(sessionRow.getStudyId());
        response.setOrderCode(sessionRow.getOrderCode());
        response.setExamTime(sessionRow.getExamTime());
        response.setPackageCode(sessionRow.getPackageCode());
        response.setPackageName(sessionRow.getPackageName());
        response.setAbnormalSummary(sessionRow.getAbnormalSummary());
        response.setFinalConclusion(sessionRow.getFinalConclusion());
        response.setAbnormalCount((int) detailRows.stream()
                .map(PatientExamResultItemResponse::getAbnormalFlag)
                .map(StringUtils::trimWhitespace)
                .filter(flag -> "1".equals(flag) || "2".equals(flag))
                .count());
        response.setDepartments(new ArrayList<>(departmentMap.values()));
        return response;
    }
}
