package com.lzke.ai.application.rule;

import org.springframework.jdbc.core.JdbcTemplate;

import lombok.extern.slf4j.Slf4j;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
public class SqlExecuteNode extends RuleNode {

    private JdbcTemplate jdbcTemplate;
    private String sqlTemplate;
    private String resultKey;
    private ResultType resultType;

    public enum ResultType {
        LIST,
        SINGLE_VALUE,
        SINGLE_ROW,
        AUTO
    }

    public SqlExecuteNode(String nodeId, JdbcTemplate jdbcTemplate, String sqlTemplate, String resultKey) {
        this(nodeId, jdbcTemplate, sqlTemplate, resultKey, ResultType.AUTO);
    }

    public SqlExecuteNode(String nodeId, JdbcTemplate jdbcTemplate, String sqlTemplate, String resultKey,
            ResultType resultType) {
        super(nodeId);
        this.jdbcTemplate = jdbcTemplate;
        this.sqlTemplate = sqlTemplate;
        this.resultKey = resultKey;
        this.resultType = resultType;
    }

    public SqlExecuteNode(String nodeId, Integer nodeGroup, JdbcTemplate jdbcTemplate, String sqlTemplate,
            String resultKey) {
        this(nodeId, nodeGroup, jdbcTemplate, sqlTemplate, resultKey, ResultType.AUTO);
    }

    public SqlExecuteNode(String nodeId, Integer nodeGroup, JdbcTemplate jdbcTemplate, String sqlTemplate,
            String resultKey, ResultType resultType) {
        super(nodeId, nodeGroup);
        this.jdbcTemplate = jdbcTemplate;
        this.sqlTemplate = sqlTemplate;
        this.resultKey = resultKey;
        this.resultType = resultType;
    }

    @Override
    public Map<String, Object> execute(Map<String, Object> input) throws Exception {
        List<Object> paramValues = new ArrayList<>();
        String preparedSql = convertToPreparedStatement(sqlTemplate, input, paramValues);

        preparedSql = cleanUpSql(preparedSql);

        log.info("Executing SQL: {}, with parameters: {}", preparedSql, paramValues);

        List<Map<String, Object>> queryResult = jdbcTemplate.queryForList(preparedSql, paramValues.toArray());

        Object resultValue = processQueryResult(queryResult);

        Map<String, Object> output = new HashMap<>(input);
        mergeResult(output, resultKey, resultValue);

        return output;
    }

    private Object processQueryResult(List<Map<String, Object>> queryResult) {
        if (queryResult == null || queryResult.isEmpty()) {
            return queryResult;
        }

        switch (resultType) {
            case LIST:
                return queryResult;

            case SINGLE_VALUE:
                if (!queryResult.isEmpty()) {
                    Map<String, Object> firstRow = queryResult.get(0);
                    if (!firstRow.isEmpty()) {
                        return firstRow.values().iterator().next();
                    }
                }
                return null;

            case SINGLE_ROW:
                return queryResult.isEmpty() ? null : queryResult.get(0);

            case AUTO:
            default:
                if (queryResult.size() == 1) {
                    Map<String, Object> singleRow = queryResult.get(0);
                    if (singleRow.size() == 1) {
                        return singleRow.values().iterator().next();
                    }
                }
                return queryResult;
        }
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

    private String convertToPreparedStatement(String template, Map<String, Object> params, List<Object> paramValues) {
        Pattern pattern = Pattern.compile("\\$\\{([^}]+)\\}");
        Matcher matcher = pattern.matcher(template);
        StringBuffer result = new StringBuffer();

        while (matcher.find()) {
            String expression = matcher.group(1);

            String paramName = expression;
            String operator = "=";

            if (expression.contains(":")) {
                String[] parts = expression.split(":", 2);
                paramName = parts[0].trim();
                operator = parts[1].trim().toUpperCase();
            }

            Object value = params.get(paramName);

            // 特殊处理分页参数
            if (isPaginationParam(paramName) && value == null) {
                matcher.appendReplacement(result, "__REMOVE_CONDITION__");
                continue;
            }

            // 对于分页参数，使用固定值替换而不是问号
            if ("pageNo".equals(paramName) || "pageNum".equals(paramName) || "offset".equals(paramName)) {
                int pageNo = value != null ? parseNumber(value, 1) : 1;
                int pageSize = parsePageSize(params);
                int offset = (pageNo - 1) * pageSize;
                matcher.appendReplacement(result, String.valueOf(offset));
                continue;
            } else if ("pageSize".equals(paramName) || "limit".equals(paramName)) {
                int pageSize = parsePageSize(params);
                matcher.appendReplacement(result, String.valueOf(pageSize));
                continue;
            }

            if (value == null || (value instanceof String && ((String) value).isEmpty())) {
                matcher.appendReplacement(result, "__REMOVE_CONDITION__");
                continue;
            }

            if (value instanceof Collection) {
                Collection<?> collection = (Collection<?>) value;
                if (collection.isEmpty()) {
                    matcher.appendReplacement(result, "__REMOVE_CONDITION__");
                    continue;
                }
                String placeholders = String.join(",", Collections.nCopies(collection.size(), "?"));
                matcher.appendReplacement(result, placeholders);
                paramValues.addAll(collection);
            } else if (value instanceof Object[]) {
                Object[] array = (Object[]) value;
                if (array.length == 0) {
                    matcher.appendReplacement(result, "__REMOVE_CONDITION__");
                    continue;
                }
                String placeholders = String.join(",", Collections.nCopies(array.length, "?"));
                matcher.appendReplacement(result, placeholders);
                paramValues.addAll(Arrays.asList(array));
            } else {
                if ("LIKE".equals(operator)) {
                    matcher.appendReplacement(result, "LIKE ?");
                    paramValues.add("%" + value + "%");
                } else if ("LIKE_LEFT".equals(operator)) {
                    matcher.appendReplacement(result, "LIKE ?");
                    paramValues.add("%" + value);
                } else if ("LIKE_RIGHT".equals(operator)) {
                    matcher.appendReplacement(result, "LIKE ?");
                    paramValues.add(value + "%");
                } else if (operator.matches(">=|>|<=|<|=|!=|<>")) {
                    matcher.appendReplacement(result, operator + " ?");
                    paramValues.add(value);
                } else {
                    matcher.appendReplacement(result, "?");
                    paramValues.add(value);
                }
            }
        }
        matcher.appendTail(result);

        return result.toString();
    }

    private boolean isPaginationParam(String paramName) {
        return paramName.matches("(?i)(pageNo|pageNum|pageSize|limit|offset)");
    }

    private int parseNumber(Object value, int defaultValue) {
        if (value == null) {
            return defaultValue;
        }
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        try {
            return Integer.parseInt(value.toString());
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    private int parsePageSize(Map<String, Object> params) {
        Object pageSizeValue = params.get("pageSize");
        if (pageSizeValue == null) {
            pageSizeValue = params.get("limit");
        }
        return parseNumber(pageSizeValue, 10); // 默认每页10条
    }

    private static String cleanUpSql(String sql) {
        // 使用更通用的表达式模式，支持函数调用（包括嵌套括号）
        // EXPR_PATTERN 匹配：列名、函数调用（支持嵌套括号）等
        String EXPR_PATTERN = "[\\w.]+(?:\\([^()]*(?:\\([^()]*\\)[^()]*)*\\))?";

        sql = sql.replaceAll(
                "(?i)\\s+AND\\s+" + EXPR_PATTERN + "\\s*(?:=|>=|>|<=|<|!=|<>|LIKE)?\\s*__REMOVE_CONDITION__", "");
        sql = sql.replaceAll(
                "(?i)\\s+OR\\s+" + EXPR_PATTERN + "\\s*(?:=|>=|>|<=|<|!=|<>|LIKE)?\\s*__REMOVE_CONDITION__", "");
        sql = sql.replaceAll(
                "(?i)" + EXPR_PATTERN + "\\s*(?:=|>=|>|<=|<|!=|<>|LIKE)?\\s*__REMOVE_CONDITION__\\s+AND\\s+", "");
        sql = sql.replaceAll(
                "(?i)" + EXPR_PATTERN + "\\s*(?:=|>=|>|<=|<|!=|<>|LIKE)?\\s*__REMOVE_CONDITION__\\s+OR\\s+", "");
        sql = sql.replaceAll(
                "(?i)WHERE\\s+" + EXPR_PATTERN + "\\s*(?:=|>=|>|<=|<|!=|<>|LIKE)?\\s*__REMOVE_CONDITION__\\s*$", "");
        sql = sql.replaceAll(
                "(?i)WHERE\\s+" + EXPR_PATTERN + "\\s*(?:=|>=|>|<=|<|!=|<>|LIKE)?\\s*__REMOVE_CONDITION__\\s+AND\\s+",
                "WHERE ");
        sql = sql.replaceAll(
                "(?i)WHERE\\s+" + EXPR_PATTERN + "\\s*(?:=|>=|>|<=|<|!=|<>|LIKE)?\\s*__REMOVE_CONDITION__\\s+OR\\s+",
                "WHERE ");

        // 优化LIMIT清理逻辑
        sql = cleanUpLimitClause(sql);

        sql = sql.replaceAll("(?i)WHERE\\s*$", "").trim();

        return sql;
    }

    private static String cleanUpLimitClause(String sql) {
        // 处理 LIMIT offset, pageSize 格式
        Pattern limitPattern = Pattern.compile(
                "(?i)\\s+LIMIT\\s*(__REMOVE_CONDITION__|[0-9]+)?\\s*(?:,\\s*(__REMOVE_CONDITION__|[0-9]+)?)?\\b");
        Matcher matcher = limitPattern.matcher(sql);
        StringBuffer result = new StringBuffer();

        while (matcher.find()) {
            String offsetPart = matcher.group(1);
            String sizePart = matcher.group(2);

            // 如果两个参数都是有效的数字，保留LIMIT子句
            if (!"__REMOVE_CONDITION__".equals(offsetPart) && !"__REMOVE_CONDITION__".equals(sizePart)) {
                // 两个参数都有效，直接替换回原样
                matcher.appendReplacement(result, matcher.group());
            } else if ("__REMOVE_CONDITION__".equals(offsetPart) && "__REMOVE_CONDITION__".equals(sizePart)) {
                // 两个参数都无效，移除整个LIMIT子句
                matcher.appendReplacement(result, "");
            } else if ("__REMOVE_CONDITION__".equals(offsetPart) && sizePart != null) {
                // offset无效但size有效，转换为 LIMIT 0,size
                try {
                    int size = Integer.parseInt(sizePart);
                    matcher.appendReplacement(result, " LIMIT 0," + size);
                } catch (NumberFormatException e) {
                    matcher.appendReplacement(result, "");
                }
            } else if (offsetPart != null && !"__REMOVE_CONDITION__".equals(offsetPart)
                    && "__REMOVE_CONDITION__".equals(sizePart)) {
                // offset有效但size无效，移除整个LIMIT子句或使用默认值
                matcher.appendReplacement(result, "");
            } else {
                // 其他情况，移除整个LIMIT子句
                matcher.appendReplacement(result, "");
            }
        }
        matcher.appendTail(result);

        return result.toString();
    }

    public static void main(String[] args) {

        String sql = "select TIMESTAMPDIFF(DAY, u.end_time,NOW()) AS diffDays from user_patient_task u where 1=1 and TIMESTAMPDIFF(DAY, u.end_time,NOW()) __REMOVE_CONDITION__";

        String sqlNew = cleanUpSql(sql);

        System.out.print(sqlNew);
    }

}
