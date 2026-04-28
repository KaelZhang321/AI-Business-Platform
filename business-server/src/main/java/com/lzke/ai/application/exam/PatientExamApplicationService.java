package com.lzke.ai.application.exam;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lecz.service.tools.core.utils.AuthUtil;
import com.lzke.ai.application.dto.UiApiInvokeRequest;
import com.lzke.ai.application.exam.dto.MyCustomerLatestExamDateResponse;
import com.lzke.ai.application.exam.dto.MyCustomerListItemResponse;
import com.lzke.ai.application.exam.dto.MyCustomerListQueryRequest;
import com.lzke.ai.application.exam.dto.MyPatientLatestExamDateResponse;
import com.lzke.ai.application.exam.dto.MyPatientListItemResponse;
import com.lzke.ai.application.exam.dto.MyPatientListQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamBatchResultQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamCleanedIndicatorResponse;
import com.lzke.ai.application.exam.dto.PatientExamCleanedResultQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamCleanedResultResponse;
import com.lzke.ai.application.exam.dto.PatientExamCleanedSummaryResponse;
import com.lzke.ai.application.exam.dto.PatientExamComparisonItemResponse;
import com.lzke.ai.application.exam.dto.PatientExamComparisonResponse;
import com.lzke.ai.application.exam.dto.PatientExamDepartmentResponse;
import com.lzke.ai.application.exam.dto.PatientExamDepartmentResultResponse;
import com.lzke.ai.application.exam.dto.PatientExamDepartmentTable;
import com.lzke.ai.application.exam.dto.PatientExamItemResultResponse;
import com.lzke.ai.application.exam.dto.PatientExamPatientInfoResponse;
import com.lzke.ai.application.exam.dto.PatientExamPatientQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamResultItemResponse;
import com.lzke.ai.application.exam.dto.PatientExamResultQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamStatsResponse;
import com.lzke.ai.application.exam.dto.PatientHisItemResultQueryRequest;
import com.lzke.ai.application.exam.dto.PatientHisItemResultResponse;
import com.lzke.ai.application.exam.dto.PatientHisReportItemResponse;
import com.lzke.ai.application.exam.dto.PatientExamSessionQueryRequest;
import com.lzke.ai.application.exam.dto.PatientExamSessionResponse;
import com.lzke.ai.application.exam.dto.PatientExamSessionRowResponse;
import com.lzke.ai.application.exam.dto.PatientExamSessionSummaryResponse;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import com.lzke.ai.application.ui.UiBuilderApplicationService;
import com.lzke.ai.infrastructure.persistence.mapper.PatientExamOdsMapper;
import com.lzke.ai.interfaces.dto.PageResult;
import com.lzke.ai.service.L1RuleCleaner;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.time.DayOfWeek;
import java.time.LocalDateTime;
import java.util.regex.Matcher;
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
    private static final Pattern REFERENCE_RANGE_PATTERN = Pattern.compile("(-?\\d+(?:\\.\\d+)?)\\s*(?:-|~|～|至)\\s*(-?\\d+(?:\\.\\d+)?)");
    private static final Pattern NUMBER_PATTERN = Pattern.compile("-?\\d+(?:\\.\\d+)?");
    private static final Set<String> TEXT_SOURCE_TABLES = Set.of("ods_tj_usb", "ods_tj_jlb");
    private static final List<String> TEXT_ITEM_KEYWORDS = List.of("超声", "结论", "所见", "描述", "提示", "检查", "影像", "PACS");
    private static final int MAX_BATCH_REPORTS = 10;
    private static final int DEFAULT_BATCH_QUERY_YEARS = 3;
    private static final String MY_CUSTOMER_ENDPOINT_ID = "6bbc18329c3dde651603182a651569ab";

    private final PatientExamOdsMapper patientExamOdsMapper;
    private final UiBuilderApplicationService uiBuilderApplicationService;
    private final ObjectMapper objectMapper;

    /**
     * 查询可选科室列表。
     */
    public List<PatientExamDepartmentResponse> listDepartments() {
        return patientExamOdsMapper.selectDepartmentTables(null).stream()
                .map(table -> new PatientExamDepartmentResponse(table.getDepartmentCode(), table.getDepartmentName()))
                .toList();
    }

    /**
     * 查询体检客户统计概览。
     *
     * <p>当前返回三项指标：
     * 最近三年有体检记录的客户数、本周体检客户数、上周体检客户数。
     */
    public PatientExamStatsResponse getExamStats() {
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime startOfThisWeek = now.toLocalDate().with(DayOfWeek.MONDAY).atStartOfDay();
        LocalDateTime startOfLastWeek = startOfThisWeek.minusWeeks(1);
        LocalDateTime startOfNextWeek = startOfThisWeek.plusWeeks(1);
        LocalDateTime startOfRecentThreeYears = now.minusYears(3);

        PatientExamStatsResponse response = new PatientExamStatsResponse();
        response.setRecentThreeYearsPatientCount(
                patientExamOdsMapper.countDistinctPatientsByExamTimeRange(startOfRecentThreeYears, now.plusSeconds(1))
        );
        response.setThisWeekPatientCount(
                patientExamOdsMapper.countDistinctPatientsByExamTimeRange(startOfThisWeek, startOfNextWeek)
        );
        response.setLastWeekPatientCount(
                patientExamOdsMapper.countDistinctPatientsByExamTimeRange(startOfLastWeek, startOfThisWeek)
        );
        return response;
    }

    /**
     * 按身份证号查询 HIS 单项检查结果。
     *
     * <p>先通过 HIS 客户表定位病历号，再合并返回 LIS 检验结果和 PACS 影像结果。
     */
    public List<PatientHisItemResultResponse> listHisItemResults(PatientHisItemResultQueryRequest request) {
        if (request == null || !StringUtils.hasText(request.getIdCard())) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "身份证号不能为空");
        }
        List<PatientHisItemResultResponse> rows = patientExamOdsMapper.selectHisItemResultsByIdCard(
                request.getIdCard().trim(),
                LocalDateTime.now().minusYears(DEFAULT_BATCH_QUERY_YEARS)
        );
        return groupHisItemResults(rows);
    }

    private List<PatientHisItemResultResponse> groupHisItemResults(List<PatientHisItemResultResponse> rows) {
        if (rows == null || rows.isEmpty()) {
            return Collections.emptyList();
        }

        List<PatientHisItemResultResponse> result = new ArrayList<>();
        Map<String, PatientHisItemResultResponse> lisGroupMap = new LinkedHashMap<>();
        for (PatientHisItemResultResponse row : rows) {
            if (!"LIS".equalsIgnoreCase(row.getResultType())) {
                row.setItems(Collections.emptyList());
                result.add(row);
                continue;
            }

            String groupKey = String.join("::",
                    nullToEmpty(row.getTestNo()),
                    nullToEmpty(row.getItemCode())
            );
            PatientHisItemResultResponse group = lisGroupMap.get(groupKey);
            if (group == null) {
                group = buildLisGroup(row);
                lisGroupMap.put(groupKey, group);
                result.add(group);
            }
            group.getItems().add(toHisReportItem(row));
        }
        return result;
    }

    private PatientHisItemResultResponse buildLisGroup(PatientHisItemResultResponse row) {
        PatientHisItemResultResponse group = new PatientHisItemResultResponse();
        group.setPatientNo(row.getPatientNo());
        group.setPatientName(row.getPatientName());
        group.setGenderName(row.getGenderName());
        group.setBirthdayDate(row.getBirthdayDate());
        group.setAge(row.getAge());
        group.setIdCard(row.getIdCard());
        group.setResultType(row.getResultType());
        group.setSourceType(row.getSourceType());
        group.setTestNo(row.getTestNo());
        group.setItemCode(row.getItemCode());
        group.setItemName(row.getItemName());
        group.setRequestedTime(row.getRequestedTime());
        group.setReportTime(row.getReportTime());
        group.setCompanyCode(row.getCompanyCode());
        group.setCompanyName(row.getCompanyName());
        group.setItems(new ArrayList<>());
        return group;
    }

    private PatientHisReportItemResponse toHisReportItem(PatientHisItemResultResponse row) {
        PatientHisReportItemResponse item = new PatientHisReportItemResponse();
        item.setReportItemCode(row.getReportItemCode());
        item.setReportItemName(row.getReportItemName());
        item.setResultValue(row.getResultValue());
        item.setPrintContext(row.getPrintContext());
        item.setUnit(row.getUnit());
        item.setAbnormalIndicator(row.getAbnormalIndicator());
        item.setRequestedTime(row.getRequestedTime());
        item.setReportTime(row.getReportTime());
        item.setUniqueId(row.getUniqueId());
        return item;
    }

    private String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private PatientExamCleanedResultResponse buildCleanedExamResult(
            PatientExamSessionRowResponse sessionRow,
            List<PatientExamResultItemResponse> detailRows
    ) {
        List<PatientExamCleanedIndicatorResponse> indicators = new ArrayList<>();
        Set<String> categories = new LinkedHashSet<>();
        for (PatientExamResultItemResponse row : detailRows) {
            if (!StringUtils.hasText(row.getItemName()) && !StringUtils.hasText(row.getResultValue())) {
                continue;
            }
            PatientExamCleanedIndicatorResponse indicator = toCleanedIndicator(row);
            if (isHiddenHealthQuestionnaireIndicator(indicator)) {
                continue;
            }
            normalizeHealthQuestionnaireValue(indicator);
            if (StringUtils.hasText(indicator.getCategory())) {
                categories.add(indicator.getCategory());
            }
            indicators.add(indicator);
        }

        PatientExamCleanedSummaryResponse summary = new PatientExamCleanedSummaryResponse();
        summary.setTotalIndicators(indicators.size());
        summary.setAbnormalCount((int) indicators.stream()
                .filter(indicator -> Boolean.TRUE.equals(indicator.getAbnormal()))
                .count());
        summary.setCategories(new ArrayList<>(categories));

        PatientExamCleanedResultResponse response = new PatientExamCleanedResultResponse();
        response.setStudyId(sessionRow.getStudyId());
        response.setPatientName(sessionRow.getPatientName());
        response.setGender(sessionRow.getGender());
        response.setExamTime(sessionRow.getExamTime());
        response.setPackageName(sessionRow.getPackageName());
        response.setSummary(summary);
        response.setIndicators(indicators);
        return response;
    }

    private boolean isHiddenHealthQuestionnaireIndicator(PatientExamCleanedIndicatorResponse indicator) {
        return isHealthQuestionnaireIndicator(indicator) && "0".equals(indicator.getValue().trim());
    }

    private void normalizeHealthQuestionnaireValue(PatientExamCleanedIndicatorResponse indicator) {
        if (isHealthQuestionnaireIndicator(indicator) && "1".equals(indicator.getValue().trim())) {
            indicator.setValue("是");
        }
    }

    private boolean isHealthQuestionnaireIndicator(PatientExamCleanedIndicatorResponse indicator) {
        return indicator != null
                && "健康问诊".equals(indicator.getCategory())
                && StringUtils.hasText(indicator.getValue());
    }

    private PatientExamCleanedIndicatorResponse toCleanedIndicator(PatientExamResultItemResponse row) {
        L1RuleCleaner.CleanResult cleanResult = L1RuleCleaner.clean(row.getItemName());
        String category = StringUtils.hasText(cleanResult.getCategory())
                ? cleanResult.getCategory()
                : row.getMajorItemName();
        ReferenceRange referenceRange = parseReferenceRange(row.getReferenceRange());
        String abnormalDirection = resolveAbnormalDirection(row.getAbnormalFlag());
        if (!StringUtils.hasText(abnormalDirection)) {
            abnormalDirection = inferAbnormalDirection(row.getResultValue(), referenceRange);
        }
        if(row.getResultValue() != null&&row.getResultValue().contains("阴性")){
        	abnormalDirection = null;
        }

        PatientExamCleanedIndicatorResponse indicator = new PatientExamCleanedIndicatorResponse();
        indicator.setStandardCode(StringUtils.hasText(cleanResult.getStandardCode())
                ? cleanResult.getStandardCode()
                : row.getItemCode());
        indicator.setStandardName(StringUtils.hasText(cleanResult.getStandardName())
                ? cleanResult.getStandardName()
                : (StringUtils.hasText(cleanResult.getCleaned()) ? cleanResult.getCleaned() : row.getItemName()));
        indicator.setCategory(category);
        indicator.setValue(row.getResultValue());
        indicator.setUnit(row.getUnit());
        indicator.setReferenceRange(row.getReferenceRange());
        indicator.setRefMin(referenceRange.min());
        indicator.setRefMax(referenceRange.max());
        indicator.setAbnormal(isAbnormal(row.getAbnormalFlag(), abnormalDirection));
        indicator.setAbnormalDirection(abnormalDirection);
        return indicator;
    }

    private ReferenceRange parseReferenceRange(String value) {
        if (!StringUtils.hasText(value)) {
            return new ReferenceRange(null, null);
        }
        Matcher matcher = REFERENCE_RANGE_PATTERN.matcher(value.trim());
        if (!matcher.find()) {
            return new ReferenceRange(null, null);
        }
        return new ReferenceRange(matcher.group(1), matcher.group(2));
    }

    private boolean isAbnormal(String abnormalFlag, String abnormalDirection) {
        if (StringUtils.hasText(abnormalDirection)) {
            return true;
        }
        if (!StringUtils.hasText(abnormalFlag)) {
            return false;
        }
        String flag = abnormalFlag.trim();
        return !"0".equals(flag) && !"N".equalsIgnoreCase(flag) && !"正常".equals(flag);
    }

    private String resolveAbnormalDirection(String abnormalFlag) {
        if (!StringUtils.hasText(abnormalFlag)) {
            return null;
        }
        String flag = abnormalFlag.trim();
        return switch (flag) {
            case "2", "H", "h", "↑", "高", "偏高" -> "high";
            case "1", "L", "l", "↓", "低", "偏低" -> "low";
            default -> null;
        };
    }

    private String inferAbnormalDirection(String resultValue, ReferenceRange referenceRange) {
        Double value = parseFirstNumber(resultValue);
        Double min = parseFirstNumber(referenceRange.min());
        Double max = parseFirstNumber(referenceRange.max());
        if (value == null) {
            return null;
        }
        if (max != null && value > max) {
            return "high";
        }
        if (min != null && value < min) {
            return "low";
        }
        return null;
    }

    private Double parseFirstNumber(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        Matcher matcher = NUMBER_PATTERN.matcher(value.trim());
        if (!matcher.find()) {
            return null;
        }
        try {
            return Double.parseDouble(matcher.group());
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private Double safeFloat(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        try {
            double number = Double.parseDouble(value.trim());
            return Double.isNaN(number) ? null : number;
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private record ReferenceRange(String min, String max) {
    }

    private static class ComparisonBucket {
        private String standardCode;
        private String standardName;
        private String category;
        private String unit;
        private final Map<String, Object> values = new LinkedHashMap<>();
        private Double refMin;
        private Double refMax;
    }

    /**
     * 查询当前登录员工的患者列表。
     *
     * <p>列表基于医疗团队表与客户基础信息表关联，再补最近一次体检时间，
     * 方便前端先展示“我的患者”入口页。
     */
    public PageResult<MyPatientListItemResponse> listMyPatients(MyPatientListQueryRequest request) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "我的患者查询请求不能为空");
        }
        Long currentUserId = AuthUtil.getUserId();
        if (currentUserId == null) {
            throw new BusinessException(ErrorCode.UNAUTHORIZED, "未获取到当前用户信息");
        }

        String staffId = String.valueOf(currentUserId);
        long total = patientExamOdsMapper.countMyPatients(staffId, request);
        if (total <= 0) {
            return PageResult.empty(request.getPage(), request.getSize());
        }

        List<MyPatientListItemResponse> data = patientExamOdsMapper.selectMyPatients(staffId, request);
        fillLatestExamDates(data);
        data.sort((left, right) -> compareLatestExamDate(right.getLatestExamDate(), left.getLatestExamDate()));
        return PageResult.of(data, total, request.getPage(), request.getSize());
    }

    /**
     * 查询我的客户列表。
     *
     * <p>该接口复用 UI Builder 已配置好的客户列表接口，避免在体检模块再次维护
     * CRM 客户列表的鉴权、参数协议和字段细节。这里仅补齐最近一次体检日期。
     */
    public PageResult<MyCustomerListItemResponse> listMyCustomers(MyCustomerListQueryRequest request) {
        if (request == null) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "我的客户查询请求不能为空");
        }

        UiApiInvokeRequest invokeRequest = new UiApiInvokeRequest();
        invokeRequest.setQueryParams(request.getQueryParams());
        invokeRequest.setBody(buildMyCustomerInvokeBody(request));
        invokeRequest.setFlowNum("listMyCustomers");
        invokeRequest.setCreatedBy(AuthUtil.getUserId() != null ? String.valueOf(AuthUtil.getUserId()) : null);
        Object invokeResult = uiBuilderApplicationService.invokeEndpoint(MY_CUSTOMER_ENDPOINT_ID, invokeRequest);

        Map<String, Object> root = objectMapper.convertValue(invokeResult, new TypeReference<LinkedHashMap<String, Object>>() {
        });
        Map<String, Object> result = toObjectMap(root.get("result"));
        List<MyCustomerListItemResponse> records = toMyCustomerItems(result.get("records"));
        fillLatestExamDatesByEncryptedIdCards(records);

        long total = toLong(result.get("total"), records.size());
        int current = toInt(result.get("current"), request.getPage());
        int size = toInt(result.get("size"), request.getSize());
        return PageResult.of(records, total, current, size);
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
     * 查询单个体检并按 L1 规则清洗指标名称。
     */
    public PatientExamCleanedResultResponse getCleanedExamResult(String studyId) {
        if (!StringUtils.hasText(studyId)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "studyId不能为空");
        }

        PatientExamSessionRowResponse sessionRow = patientExamOdsMapper.selectPatientExamSessionByStudyId(studyId);
        if (sessionRow == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到对应体检记录: " + studyId);
        }

        List<PatientExamDepartmentTable> tables = patientExamOdsMapper.selectDepartmentTables(null);
        List<PatientExamDepartmentTable> resolvedTables = resolveTables(tables);
        List<PatientExamResultItemResponse> detailRows = resolvedTables.isEmpty()
                ? Collections.emptyList()
                : patientExamOdsMapper.selectPatientExamDepartmentItems(
                        Collections.singletonList(studyId),
                        resolvedTables
                );
        return buildCleanedExamResult(sessionRow, detailRows);
    }

    /**
     * 按患者身份证号纵向对比多次体检指标。
     *
     * <p>实现逻辑对齐 zbqx 的 {@code /patient/{sfzh}/comparison}：
     * numeric 模式对比数值指标，text 模式对比影像/结论类文本指标。
     */
    public PatientExamComparisonResponse getPatientComparison(String idCard, String category, String mode) {
        if (!StringUtils.hasText(idCard)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "身份证号不能为空");
        }
        String normalizedMode = StringUtils.hasText(mode) ? mode.trim().toLowerCase(Locale.ROOT) : "numeric";
        if (!"numeric".equals(normalizedMode) && !"text".equals(normalizedMode)) {
            throw new BusinessException(ErrorCode.BAD_REQUEST, "mode只支持numeric或text");
        }

        PatientExamBatchResultQueryRequest request = new PatientExamBatchResultQueryRequest();
        request.setIdCard(idCard.trim());
        List<PatientExamSessionResponse> sessions = getBatchExamResults(request);
        if (sessions.isEmpty()) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, "未找到该患者体检记录");
        }

        Map<String, ComparisonBucket> merged = new LinkedHashMap<>();
        Set<String> examDates = new LinkedHashSet<>();
        for (PatientExamSessionResponse session : sessions) {
            String examDate = toExamDate(session.getExamTime());
            if (!StringUtils.hasText(examDate) || session.getDepartments() == null) {
                continue;
            }

            for (PatientExamDepartmentResultResponse department : session.getDepartments()) {
                if (department.getItems() == null) {
                    continue;
                }
                for (PatientExamItemResultResponse item : department.getItems()) {
                    mergeComparisonItem(merged, examDates, examDate, department, item, category, normalizedMode);
                }
            }
        }

        List<String> sortedDates = new ArrayList<>(examDates);
        Collections.sort(sortedDates);

        PatientExamComparisonResponse response = new PatientExamComparisonResponse();
        response.setPatientId(maskIdCard(idCard.trim()));
        response.setMode(normalizedMode);
        response.setExamDates(sortedDates);
        response.setComparisons(buildComparisonItems(merged, sortedDates, normalizedMode));
        return response;
    }

    private void mergeComparisonItem(
            Map<String, ComparisonBucket> merged,
            Set<String> examDates,
            String examDate,
            PatientExamDepartmentResultResponse department,
            PatientExamItemResultResponse item,
            String category,
            String mode
    ) {
        String itemName = item.getItemName();
        L1RuleCleaner.CleanResult cleanResult = L1RuleCleaner.clean(itemName);
        String code = StringUtils.hasText(cleanResult.getStandardCode()) ? cleanResult.getStandardCode() : nullToEmpty(item.getItemCode());
        String name = StringUtils.hasText(cleanResult.getStandardName()) ? cleanResult.getStandardName() : cleanResult.getCleaned();
        String itemCategory = nullToEmpty(cleanResult.getCategory());

        if (StringUtils.hasText(category) && !category.trim().equals(itemCategory)) {
            return;
        }
        examDates.add(examDate);

        boolean textModeRow = isTextModeRow(department, item);
        if ("text".equals(mode)) {
            if (!textModeRow) {
                return;
            }
            String textValue = normalizeTextValue(item.getResultValue());
            if (!StringUtils.hasText(textValue)) {
                return;
            }
            ComparisonBucket bucket = merged.computeIfAbsent(code, key -> {
                ComparisonBucket created = new ComparisonBucket();
                created.standardCode = code;
                created.standardName = name;
                created.category = StringUtils.hasText(itemCategory) ? itemCategory : "影像/结论";
                created.unit = "";
                return created;
            });
            bucket.values.put(examDate, textValue);
            return;
        }

        if (textModeRow) {
            return;
        }
        Double numeric = safeFloat(item.getResultValue());
        ComparisonBucket bucket = merged.computeIfAbsent(code, key -> {
            ReferenceRange referenceRange = parseReferenceRange(item.getReferenceRange());
            ComparisonBucket created = new ComparisonBucket();
            created.standardCode = code;
            created.standardName = name;
            created.category = itemCategory;
            created.unit = nullToEmpty(item.getUnit());
            created.refMin = safeFloat(referenceRange.min());
            created.refMax = safeFloat(referenceRange.max());
            return created;
        });
        bucket.values.put(examDate, numeric);
    }

    private List<PatientExamComparisonItemResponse> buildComparisonItems(
            Map<String, ComparisonBucket> merged,
            List<String> sortedDates,
            String mode
    ) {
        List<PatientExamComparisonItemResponse> comparisons = new ArrayList<>();
        for (ComparisonBucket bucket : merged.values()) {
            PatientExamComparisonItemResponse item = new PatientExamComparisonItemResponse();
            item.setStandardCode(bucket.standardCode);
            item.setStandardName(bucket.standardName);
            item.setCategory(bucket.category);
            item.setUnit(bucket.unit);
            item.setValues(bucket.values);
            item.setTrend(resolveComparisonTrend(bucket.values, sortedDates, mode));
            item.setRefMin(bucket.refMin);
            item.setRefMax(bucket.refMax);
            comparisons.add(item);
        }
        return comparisons;
    }

    private String resolveComparisonTrend(Map<String, Object> values, List<String> sortedDates, String mode) {
        if ("text".equals(mode)) {
            List<Object> orderedValues = sortedDates.stream()
                    .filter(values::containsKey)
                    .map(values::get)
                    .toList();
            if (orderedValues.size() < 2) {
                return "";
            }
            Object previous = orderedValues.get(orderedValues.size() - 2);
            Object current = orderedValues.get(orderedValues.size() - 1);
            return Objects.equals(previous, current) && current != null ? "一致" : "变化";
        }

        if (sortedDates.size() < 2) {
            return "";
        }
        Object previous = values.get(sortedDates.get(sortedDates.size() - 2));
        Object current = values.get(sortedDates.get(sortedDates.size() - 1));
        if (!(previous instanceof Number previousNumber) || !(current instanceof Number currentNumber)) {
            return "";
        }
        int compare = Double.compare(currentNumber.doubleValue(), previousNumber.doubleValue());
        if (compare > 0) {
            return "↑";
        }
        if (compare < 0) {
            return "↓";
        }
        return "=";
    }

    private boolean isTextModeRow(PatientExamDepartmentResultResponse department, PatientExamItemResultResponse item) {
        String sourceTable = nullToEmpty(department.getSourceTable()).toLowerCase(Locale.ROOT);
        if (TEXT_SOURCE_TABLES.contains(sourceTable)) {
            return true;
        }
        String itemName = nullToEmpty(item.getItemName());
        String itemNameEn = nullToEmpty(item.getItemNameEn());
        if (TEXT_ITEM_KEYWORDS.stream().anyMatch(keyword -> itemName.contains(keyword) || itemNameEn.contains(keyword))) {
            return true;
        }
        String rawValue = nullToEmpty(item.getResultValue()).trim();
        return StringUtils.hasText(rawValue) && safeFloat(rawValue) == null;
    }

    private String normalizeTextValue(String value) {
        return nullToEmpty(value).trim().replaceAll("\\s+", " ");
    }

    private String toExamDate(String examTime) {
        if (!StringUtils.hasText(examTime)) {
            return null;
        }
        String trimmed = examTime.trim();
        return trimmed.length() >= 10 ? trimmed.substring(0, 10) : trimmed;
    }

    private String maskIdCard(String idCard) {
        if (!StringUtils.hasText(idCard) || idCard.length() <= 8) {
            return idCard;
        }
        return idCard.substring(0, 4) + "****" + idCard.substring(idCard.length() - 4);
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
            sessionRows = patientExamOdsMapper.selectPatientExamSessionsByIdCard(
                    normalizedIdCard,
                    LocalDateTime.now().minusYears(DEFAULT_BATCH_QUERY_YEARS)
            );
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

    private void fillLatestExamDates(List<MyPatientListItemResponse> patients) {
        if (patients == null || patients.isEmpty()) {
            return;
        }

        List<String> idCards = patients.stream()
                .map(MyPatientListItemResponse::getIdCard)
                .filter(StringUtils::hasText)
                .map(String::trim)
                .distinct()
                .toList();
        if (idCards.isEmpty()) {
            return;
        }

        Map<String, String> latestExamDateMap = patientExamOdsMapper.selectLatestExamDatesByIdCards(idCards).stream()
                .filter(item -> StringUtils.hasText(item.getIdCard()))
                .collect(Collectors.toMap(
                        item -> item.getIdCard().trim(),
                        MyPatientLatestExamDateResponse::getLatestExamDate,
                        (left, right) -> left,
                        LinkedHashMap::new
                ));

        for (MyPatientListItemResponse patient : patients) {
            if (!StringUtils.hasText(patient.getIdCard())) {
                continue;
            }
            patient.setLatestExamDate(latestExamDateMap.get(patient.getIdCard().trim()));
        }
    }

    /**
     * 为客户列表补齐最近一次体检时间。
     *
     * <p>上游返回的是加密身份证，因此这里在数据库侧解密后再匹配 ODS 体检主表。
     */
    private void fillLatestExamDatesByEncryptedIdCards(List<MyCustomerListItemResponse> customers) {
        if (customers == null || customers.isEmpty()) {
            return;
        }

        List<String> encryptedIdCards = customers.stream()
                .map(MyCustomerListItemResponse::getEncryptedIdCard)
                .filter(StringUtils::hasText)
                .map(String::trim)
                .distinct()
                .toList();
        if (encryptedIdCards.isEmpty()) {
            return;
        }

        List<MyCustomerLatestExamDateResponse> latestExamDateRows = patientExamOdsMapper.selectLatestExamDatesByEncryptedIdCards(encryptedIdCards);
        if (latestExamDateRows == null || latestExamDateRows.isEmpty()) {
            return;
        }

        Map<String, String> latestExamDateMap = latestExamDateRows.stream()
                .filter(Objects::nonNull)
                .filter(item -> StringUtils.hasText(item.getEncryptedIdCard()))
                .filter(item -> StringUtils.hasText(item.getLatestExamDate()))
                .collect(Collectors.toMap(
                        item -> item.getEncryptedIdCard().trim(),
                        MyCustomerLatestExamDateResponse::getLatestExamDate,
                        (left, right) -> left,
                        LinkedHashMap::new
                ));

        for (MyCustomerListItemResponse customer : customers) {
            if (!StringUtils.hasText(customer.getEncryptedIdCard())) {
                continue;
            }
            customer.setLatestExamDate(latestExamDateMap.get(customer.getEncryptedIdCard().trim()));
        }
    }

    private int compareLatestExamDate(String left, String right) {
        if (!StringUtils.hasText(left) && !StringUtils.hasText(right)) {
            return 0;
        }
        if (!StringUtils.hasText(left)) {
            return -1;
        }
        if (!StringUtils.hasText(right)) {
            return 1;
        }
        return left.compareTo(right);
    }

    /**
     * 组装“我的客户列表”上游请求体。
     *
     * <p>页面只关心分页时，默认补 current/size；如果前端 body 已显式传值，则优先尊重前端。
     */
    private Map<String, Object> buildMyCustomerInvokeBody(MyCustomerListQueryRequest request) {
        Map<String, Object> body = new LinkedHashMap<>();
        if (request.getBody() != null) {
            body.putAll(request.getBody());
        }
        body.putIfAbsent("pageNo", request.getPage());
        body.putIfAbsent("pageSize", request.getSize());
        return body;
    }

    /**
     * 将上游 records 转成前端列表项。
     */
    private List<MyCustomerListItemResponse> toMyCustomerItems(Object recordsObject) {
        if (!(recordsObject instanceof List<?> rawRecords) || rawRecords.isEmpty()) {
            return Collections.emptyList();
        }
        List<MyCustomerListItemResponse> items = new ArrayList<>(rawRecords.size());
        for (Object rawRecord : rawRecords) {
            Map<String, Object> record = toObjectMap(rawRecord);
            MyCustomerListItemResponse item = new MyCustomerListItemResponse();
            item.setCustomerId(asString(record.get("id")));
            item.setPatientName(asString(record.get("name")));
            item.setGender(asString(record.get("sex")));
            item.setAge(toNullableInt(record.get("age")));
            item.setEncryptedIdCard(asString(record.get("idCard")));
            item.setIdCardObfuscated(asString(record.get("idCardObfuscated")));
            item.setEncryptedPhone(asString(record.get("phone")));
            item.setPhoneObfuscated(asString(record.get("phoneObfuscated")));
            item.setTypeName(asString(record.get("typeName")));
            item.setStoreName(asString(record.get("storeName")));
            item.setMainTeacherName(asString(record.get("mainTeacherName")));
            item.setSubTeacherName(asString(record.get("subTeacherName")));
            items.add(item);
        }
        return items;
    }

    private Map<String, Object> toObjectMap(Object value) {
        if (value == null) {
            return Collections.emptyMap();
        }
        return objectMapper.convertValue(value, new TypeReference<LinkedHashMap<String, Object>>() {
        });
    }

    private String asString(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private int toInt(Object value, int defaultValue) {
        if (value == null) {
            return defaultValue;
        }
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException ex) {
            return defaultValue;
        }
    }

    private long toLong(Object value, long defaultValue) {
        if (value == null) {
            return defaultValue;
        }
        if (value instanceof Number number) {
            return number.longValue();
        }
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException ex) {
            return defaultValue;
        }
    }

    private Integer toNullableInt(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException ex) {
            return null;
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
