package com.lzke.ai.application.rule;

import java.util.*;
import java.util.function.Predicate;
import java.util.stream.Collectors;

public class ParseResultNode extends RuleNode {

    private String sourceKey;
    private String targetKey;
    private ParseType parseType;
    private String columnName;
    private FilterCondition filterCondition;

    public enum ParseType {
        TO_LIST,
        TO_STRING_ARRAY,
        TO_MAP_LIST,
        EXTRACT_COLUMN
    }

    public enum FilterOperator {
        EQUALS,
        NOT_EQUALS,
        GREATER_THAN,
        GREATER_THAN_OR_EQUAL,
        LESS_THAN,
        LESS_THAN_OR_EQUAL,
        LIKE,
        IN,
        NOT_IN
    }

    public static class FilterCondition {
        private String columnName;
        private FilterOperator operator;
        private Object value;

        public FilterCondition(String columnName, FilterOperator operator, Object value) {
            this.columnName = columnName;
            this.operator = operator;
            this.value = value;
        }

        public String getColumnName() {
            return columnName;
        }

        public FilterOperator getOperator() {
            return operator;
        }

        public Object getValue() {
            return value;
        }
    }

    public ParseResultNode(String nodeId, String sourceKey, String targetKey, ParseType parseType, String columnName) {
        super(nodeId);
        this.sourceKey = sourceKey;
        this.targetKey = targetKey;
        this.parseType = parseType;
        this.columnName = columnName;
    }

    public ParseResultNode(String nodeId, String sourceKey, String targetKey, ParseType parseType) {
        this(nodeId, sourceKey, targetKey, parseType, null);
    }

    public ParseResultNode(String nodeId, String sourceKey, String targetKey, ParseType parseType, String columnName, FilterCondition filterCondition) {
        this(nodeId, sourceKey, targetKey, parseType, columnName);
        this.filterCondition = filterCondition;
    }

    public ParseResultNode(String nodeId, Integer nodeGroup, String sourceKey, String targetKey, ParseType parseType, String columnName) {
        super(nodeId, nodeGroup);
        this.sourceKey = sourceKey;
        this.targetKey = targetKey;
        this.parseType = parseType;
        this.columnName = columnName;
    }

    public ParseResultNode(String nodeId, Integer nodeGroup, String sourceKey, String targetKey, ParseType parseType, String columnName, FilterCondition filterCondition) {
        this(nodeId, nodeGroup, sourceKey, targetKey, parseType, columnName);
        this.filterCondition = filterCondition;
    }

    @Override
    public Map<String, Object> execute(Map<String, Object> input) throws Exception {
        Object sourceData = input.get(sourceKey);

        if (!(sourceData instanceof List)) {
            throw new IllegalArgumentException("Source data is not a List");
        }

        List<Map<String, Object>> sourceList = (List<Map<String, Object>>) sourceData;

        if (filterCondition != null) {
            sourceList = applyFilter(sourceList, filterCondition);
        }

        Object parsedResult = null;

        switch (parseType) {
            case TO_LIST:
                parsedResult = sourceList;
                break;

            case TO_STRING_ARRAY:
                parsedResult = extractColumnToStringArray(sourceList, columnName);
                break;

            case EXTRACT_COLUMN:
                parsedResult = extractColumnToList(sourceList, columnName);
                break;

            case TO_MAP_LIST:
                parsedResult = sourceList;
                break;

            default:
                throw new IllegalArgumentException("Unsupported parse type: " + parseType);
        }

        Map<String, Object> output = new HashMap<>(input);
        mergeResult(output, targetKey, parsedResult);

        return output;
    }

    private void mergeResult(Map<String, Object> output, String key, Object newValue) {
        if (output.containsKey(key)) {
            Object existingValue = output.get(key);
            
            if (existingValue instanceof List && newValue instanceof List) {
                List<Object> mergedList = new ArrayList<>((List<?>) existingValue);
                mergedList.addAll((List<?>) newValue);
                output.put(key, mergedList);
            } else if (existingValue instanceof Object[] && newValue instanceof Object[]) {
                Object[] existing = (Object[]) existingValue;
                Object[] newArr = (Object[]) newValue;
                Object[] merged = new Object[existing.length + newArr.length];
                System.arraycopy(existing, 0, merged, 0, existing.length);
                System.arraycopy(newArr, 0, merged, existing.length, newArr.length);
                output.put(key, merged);
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

    private List<Map<String, Object>> applyFilter(List<Map<String, Object>> dataList, FilterCondition condition) {
        return dataList.stream()
                .filter(row -> matchCondition(row, condition))
                .collect(Collectors.toList());
    }

    private boolean matchCondition(Map<String, Object> row, FilterCondition condition) {
        Object columnValue = row.get(condition.getColumnName());
        Object filterValue = condition.getValue();

        if (columnValue == null) {
            return false;
        }

        switch (condition.getOperator()) {
            case EQUALS:
                return columnValue.equals(filterValue);

            case NOT_EQUALS:
                return !columnValue.equals(filterValue);

            case GREATER_THAN:
                return compareValues(columnValue, filterValue) > 0;

            case GREATER_THAN_OR_EQUAL:
                return compareValues(columnValue, filterValue) >= 0;

            case LESS_THAN:
                return compareValues(columnValue, filterValue) < 0;

            case LESS_THAN_OR_EQUAL:
                return compareValues(columnValue, filterValue) <= 0;

            case LIKE:
                return String.valueOf(columnValue).contains(String.valueOf(filterValue));

            case IN:
                if (filterValue instanceof Collection) {
                    return ((Collection<?>) filterValue).contains(columnValue);
                } else if (filterValue instanceof Object[]) {
                    return Arrays.asList((Object[]) filterValue).contains(columnValue);
                }
                return false;

            case NOT_IN:
                if (filterValue instanceof Collection) {
                    return !((Collection<?>) filterValue).contains(columnValue);
                } else if (filterValue instanceof Object[]) {
                    return !Arrays.asList((Object[]) filterValue).contains(columnValue);
                }
                return true;

            default:
                return false;
        }
    }

    @SuppressWarnings("unchecked")
    private int compareValues(Object value1, Object value2) {
        if (value1 instanceof Comparable && value2 instanceof Comparable) {
            return ((Comparable) value1).compareTo(value2);
        }
        return 0;
    }

    private String[] extractColumnToStringArray(List<Map<String, Object>> dataList, String column) {
        return dataList.stream()
                .map(map -> map.get(column))
                .filter(Objects::nonNull)
                .map(String::valueOf)
                .toArray(String[]::new);
    }

    private List<Object> extractColumnToList(List<Map<String, Object>> dataList, String column) {
        return dataList.stream()
                .map(map -> map.get(column))
                .filter(Objects::nonNull)
                .collect(Collectors.toList());
    }
}
