package com.lzke.ai.application.rule;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;

public class CalculateNode extends RuleNode {

    private String expression;
    private String resultKey;
    private Integer scale;
    private RoundingMode roundingMode;

    public enum Operator {
        ADD("+"),
        SUBTRACT("-"),
        MULTIPLY("*"),
        DIVIDE("/");

        private String symbol;

        Operator(String symbol) {
            this.symbol = symbol;
        }

        public String getSymbol() {
            return symbol;
        }

        public static Operator fromSymbol(String symbol) {
            for (Operator op : values()) {
                if (op.symbol.equals(symbol)) {
                    return op;
                }
            }
            throw new IllegalArgumentException("Unsupported operator: " + symbol);
        }
    }

    public CalculateNode(String nodeId, String expression, String resultKey) {
        this(nodeId, expression, resultKey, 2, RoundingMode.HALF_UP);
    }

    public CalculateNode(String nodeId, String expression, String resultKey, Integer scale, RoundingMode roundingMode) {
        super(nodeId);
        this.expression = expression;
        this.resultKey = resultKey;
        this.scale = scale;
        this.roundingMode = roundingMode;
    }

    public CalculateNode(String nodeId, Integer nodeGroup, String expression, String resultKey) {
        this(nodeId, nodeGroup, expression, resultKey, 2, RoundingMode.HALF_UP);
    }

    public CalculateNode(String nodeId, Integer nodeGroup, String expression, String resultKey, Integer scale, RoundingMode roundingMode) {
        super(nodeId, nodeGroup);
        this.expression = expression;
        this.resultKey = resultKey;
        this.scale = scale;
        this.roundingMode = roundingMode;
    }

    @Override
    public Map<String, Object> execute(Map<String, Object> input) throws Exception {
        BigDecimal result = evaluate(expression, input);

        Map<String, Object> output = new HashMap<>(input);
        mergeResult(output, resultKey, result);

        return output;
    }

    private void mergeResult(Map<String, Object> output, String key, BigDecimal newValue) {
        if (output.containsKey(key)) {
            Object existingValue = output.get(key);
            
            if (existingValue instanceof Number) {
                BigDecimal existing = new BigDecimal(existingValue.toString());
                BigDecimal merged = existing.add(newValue);
                output.put(key, merged);
            } else if (existingValue instanceof List) {
                List<Object> list = new ArrayList<>((List<?>) existingValue);
                list.add(newValue);
                output.put(key, list);
            } else {
                output.put(key, newValue);
            }
        } else {
            output.put(key, newValue);
        }
    }

    private BigDecimal evaluate(String expr, Map<String, Object> context) throws Exception {
        expr = expr.trim();

        for (Operator op : new Operator[]{Operator.ADD, Operator.SUBTRACT}) {
            int lastIndex = expr.lastIndexOf(op.getSymbol());
            if (lastIndex > 0) {
                String left = expr.substring(0, lastIndex).trim();
                String right = expr.substring(lastIndex + 1).trim();

                BigDecimal leftValue = evaluate(left, context);
                BigDecimal rightValue = evaluate(right, context);

                if (op == Operator.ADD) {
                    return leftValue.add(rightValue);
                } else {
                    return leftValue.subtract(rightValue);
                }
            }
        }

        for (Operator op : new Operator[]{Operator.MULTIPLY, Operator.DIVIDE}) {
            int lastIndex = expr.lastIndexOf(op.getSymbol());
            if (lastIndex > 0) {
                String left = expr.substring(0, lastIndex).trim();
                String right = expr.substring(lastIndex + 1).trim();

                BigDecimal leftValue = evaluate(left, context);
                BigDecimal rightValue = evaluate(right, context);

                if (op == Operator.MULTIPLY) {
                    return leftValue.multiply(rightValue);
                } else {
                    if (rightValue.compareTo(BigDecimal.ZERO) == 0) {
                        throw new ArithmeticException("Division by zero");
                    }
                    return leftValue.divide(rightValue, scale, roundingMode);
                }
            }
        }

        if (expr.startsWith("(") && expr.endsWith(")")) {
            return evaluate(expr.substring(1, expr.length() - 1), context);
        }

        if (expr.startsWith("${") && expr.endsWith("}")) {
            String path = expr.substring(2, expr.length() - 1);
            return getValueFromContext(path, context);
        }

        try {
            return new BigDecimal(expr);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("Invalid expression: " + expr);
        }
    }

    private BigDecimal getValueFromContext(String path, Map<String, Object> context) {
        String[] parts = path.split("\\.");
        Object current = context;

        for (String part : parts) {
            if (current instanceof Map) {
                current = ((Map<?, ?>) current).get(part);
            } else if (current instanceof List) {
                try {
                    int index = Integer.parseInt(part);
                    current = ((List<?>) current).get(index);
                } catch (NumberFormatException e) {
                    throw new IllegalArgumentException("Invalid list index: " + part);
                }
            } else {
                throw new IllegalArgumentException("Cannot access property: " + part);
            }

            if (current == null) {
                throw new IllegalArgumentException("Value not found for path: " + path);
            }
        }

        if (current instanceof Number) {
            return new BigDecimal(current.toString());
        } else {
            throw new IllegalArgumentException("Value is not a number: " + path);
        }
    }
}
