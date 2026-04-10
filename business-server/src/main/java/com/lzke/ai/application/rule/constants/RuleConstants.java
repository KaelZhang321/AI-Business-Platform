package com.lzke.ai.application.rule.constants;

public class RuleConstants {

    public static class NodeType {
        public static final String INPUT_NODE = "INPUT_NODE";
        public static final String SQL_EXECUTE_NODE = "SQL_EXECUTE_NODE";
        public static final String PARSE_RESULT_NODE = "PARSE_RESULT_NODE";
        public static final String AGGREGATE_NODE = "AGGREGATE_NODE";
        public static final String CALCULATE_NODE = "CALCULATE_NODE";
        public static final String HTTP_REQUEST_NODE = "HTTP_REQUEST_NODE";
    }

    public static class RuleStatus {
        public static final String DRAFT = "0";
        public static final String ACTIVE = "1";
        public static final String INACTIVE = "2";
        public static final String DELETED = "-1";
    }

    public static class ParseType {
        public static final String TO_LIST = "TO_LIST";
        public static final String TO_STRING_ARRAY = "TO_STRING_ARRAY";
        public static final String TO_MAP_LIST = "TO_MAP_LIST";
        public static final String EXTRACT_COLUMN = "EXTRACT_COLUMN";
    }
}
