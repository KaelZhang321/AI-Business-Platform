package com.lzke.ai.application.rule;

import java.util.*;
import java.util.regex.Pattern;

public class InputNode extends RuleNode {

    private Map<String, Object> inputParams;
    private List<ValidationRule> validationRules;

    public enum ValidationType {
        NULL,
        NOT_NULL,
        NOT_EMPTY,
        EMAIL,
        MOBILE,
        ID_CARD,
        REGEX,
        MIN_LENGTH,
        MAX_LENGTH,
        MIN_VALUE,
        MAX_VALUE
    }

    public static class ValidationRule {
        private String paramName;
        private ValidationType type;
        private Object value;
        private String message;

        public ValidationRule(String paramName, ValidationType type) {
            this(paramName, type, null, null);
        }

        public ValidationRule(String paramName, ValidationType type, Object value) {
            this(paramName, type, value, null);
        }

        public ValidationRule(String paramName, ValidationType type, Object value, String message) {
            this.paramName = paramName;
            this.type = type;
            this.value = value;
            this.message = message;
        }

        public String getParamName() {
            return paramName;
        }

        public ValidationType getType() {
            return type;
        }

        public Object getValue() {
            return value;
        }

        public String getMessage() {
            return message;
        }
    }

    public InputNode(String nodeId, Map<String, Object> inputParams) {
        this(nodeId, inputParams, null);
    }

    public InputNode(String nodeId, Map<String, Object> inputParams, List<ValidationRule> validationRules) {
        super(nodeId);
        this.inputParams = inputParams;
        this.validationRules = validationRules;
    }

    public InputNode(String nodeId, Integer nodeGroup, Map<String, Object> inputParams) {
        this(nodeId, nodeGroup, inputParams, null);
    }

    public InputNode(String nodeId, Integer nodeGroup, Map<String, Object> inputParams, List<ValidationRule> validationRules) {
        super(nodeId, nodeGroup);
        this.inputParams = inputParams;
        this.validationRules = validationRules;
    }

    @Override
    public Map<String, Object> execute(Map<String, Object> input) throws Exception {
        if (validationRules != null && !validationRules.isEmpty()) {
            validateParams(inputParams);
        }
        return inputParams;
    }

    private void validateParams(Map<String, Object> params) throws Exception {
        for (ValidationRule rule : validationRules) {
            String paramName = rule.getParamName();
            Object paramValue = params.get(paramName);

            switch (rule.getType()) {
                case NOT_NULL:
                    if (paramValue == null) {
                        throw new IllegalArgumentException(
                            rule.getMessage() != null ? rule.getMessage() : "参数 " + paramName + " 不能为空"
                        );
                    }
                    break;

                case NOT_EMPTY:
                    if (paramValue == null || (paramValue instanceof String && ((String) paramValue).isEmpty())) {
                        throw new IllegalArgumentException(
                            rule.getMessage() != null ? rule.getMessage() : "参数 " + paramName + " 不能为空"
                        );
                    }
                    break;

                case EMAIL:
                    if (paramValue != null) {
                        String email = String.valueOf(paramValue);
                        if (!Pattern.matches("^[a-zA-Z0-9_+&*-]+(?:\\.[a-zA-Z0-9_+&*-]+)*@(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,7}$", email)) {
                            throw new IllegalArgumentException(
                                rule.getMessage() != null ? rule.getMessage() : "参数 " + paramName + " 不是有效的邮箱地址"
                            );
                        }
                    }
                    break;

                case MOBILE:
                    if (paramValue != null) {
                        String mobile = String.valueOf(paramValue);
                        if (!Pattern.matches("^1[3-9]\\d{9}$", mobile)) {
                            throw new IllegalArgumentException(
                                rule.getMessage() != null ? rule.getMessage() : "参数 " + paramName + " 不是有效的手机号"
                            );
                        }
                    }
                    break;

                case ID_CARD:
                    if (paramValue != null) {
                        String idCard = String.valueOf(paramValue);
                        if (!Pattern.matches("^[1-9]\\d{5}(18|19|20)\\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\\d|3[01])\\d{3}[\\dXx]$", idCard)) {
                            throw new IllegalArgumentException(
                                rule.getMessage() != null ? rule.getMessage() : "参数 " + paramName + " 不是有效的身份证号"
                            );
                        }
                    }
                    break;

                case REGEX:
                    if (paramValue != null && rule.getValue() != null) {
                        String value = String.valueOf(paramValue);
                        String regex = String.valueOf(rule.getValue());
                        if (!Pattern.matches(regex, value)) {
                            throw new IllegalArgumentException(
                                rule.getMessage() != null ? rule.getMessage() : "参数 " + paramName + " 格式不正确"
                            );
                        }
                    }
                    break;

                case MIN_LENGTH:
                    if (paramValue != null && rule.getValue() != null) {
                        String value = String.valueOf(paramValue);
                        int minLength = Integer.parseInt(String.valueOf(rule.getValue()));
                        if (value.length() < minLength) {
                            throw new IllegalArgumentException(
                                rule.getMessage() != null ? rule.getMessage() : "参数 " + paramName + " 长度不能小于 " + minLength
                            );
                        }
                    }
                    break;

                case MAX_LENGTH:
                    if (paramValue != null && rule.getValue() != null) {
                        String value = String.valueOf(paramValue);
                        int maxLength = Integer.parseInt(String.valueOf(rule.getValue()));
                        if (value.length() > maxLength) {
                            throw new IllegalArgumentException(
                                rule.getMessage() != null ? rule.getMessage() : "参数 " + paramName + " 长度不能大于 " + maxLength
                            );
                        }
                    }
                    break;

                case MIN_VALUE:
                    if (paramValue != null && rule.getValue() != null) {
                        double value = Double.parseDouble(String.valueOf(paramValue));
                        double minValue = Double.parseDouble(String.valueOf(rule.getValue()));
                        if (value < minValue) {
                            throw new IllegalArgumentException(
                                rule.getMessage() != null ? rule.getMessage() : "参数 " + paramName + " 值不能小于 " + minValue
                            );
                        }
                    }
                    break;

                case MAX_VALUE:
                    if (paramValue != null && rule.getValue() != null) {
                        double value = Double.parseDouble(String.valueOf(paramValue));
                        double maxValue = Double.parseDouble(String.valueOf(rule.getValue()));
                        if (value > maxValue) {
                            throw new IllegalArgumentException(
                                rule.getMessage() != null ? rule.getMessage() : "参数 " + paramName + " 值不能大于 " + maxValue
                            );
                        }
                    }
                    break;
            }
        }
    }
}
