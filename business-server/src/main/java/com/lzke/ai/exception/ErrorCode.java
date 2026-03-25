package com.lzke.ai.exception;

import lombok.Getter;

/**
 * 统一错误码枚举 — 码段划分：
 * <ul>
 *   <li>1xxx — 通用错误</li>
 *   <li>2xxx — 认证/授权</li>
 *   <li>3xxx — AI 服务</li>
 *   <li>4xxx — 知识库</li>
 *   <li>5xxx — 工作流</li>
 *   <li>6xxx — 业务规则</li>
 *   <li>7xxx — 外部系统</li>
 * </ul>
 */
@Getter
public enum ErrorCode {

    // ── 1xxx 通用 ───────────────────────────────────────────
    SUCCESS(0, "success"),
    BAD_REQUEST(1000, "请求参数错误"),
    VALIDATION_FAILED(1001, "参数校验失败"),
    RESOURCE_NOT_FOUND(1002, "资源不存在"),
    METHOD_NOT_ALLOWED(1003, "请求方法不支持"),
    RATE_LIMITED(1004, "请求过于频繁"),
    INTERNAL_ERROR(1999, "系统内部错误"),

    // ── 2xxx 认证/授权 ──────────────────────────────────────
    UNAUTHORIZED(2000, "未认证"),
    TOKEN_EXPIRED(2001, "Token 已过期"),
    TOKEN_INVALID(2002, "Token 无效"),
    REFRESH_TOKEN_INVALID(2003, "Refresh Token 无效"),
    ACCOUNT_NOT_FOUND(2004, "账号不存在"),
    ACCOUNT_DISABLED(2005, "账号已禁用"),
    PASSWORD_INCORRECT(2006, "用户名或密码错误"),
    PERMISSION_DENIED(2007, "权限不足"),

    // ── 3xxx AI 服务 ────────────────────────────────────────
    AI_SERVICE_UNAVAILABLE(3000, "AI 服务不可用"),
    MODEL_NOT_FOUND(3001, "模型不存在"),
    LLM_CALL_FAILED(3002, "LLM 调用失败"),
    INTENT_CLASSIFY_FAILED(3003, "意图分类失败"),
    TEXT2SQL_FAILED(3004, "Text2SQL 执行失败"),
    TEXT2SQL_UNSAFE(3005, "SQL 安全检查未通过"),

    // ── 4xxx 知识库 ─────────────────────────────────────────
    KNOWLEDGE_BASE_NOT_FOUND(4000, "知识库不存在"),
    DOCUMENT_NOT_FOUND(4001, "文档不存在"),
    DOCUMENT_UPLOAD_FAILED(4002, "文档上传失败"),
    DOCUMENT_PROCESS_FAILED(4003, "文档处理失败"),
    RAG_SEARCH_FAILED(4004, "知识检索失败"),
    FILE_TYPE_NOT_SUPPORTED(4005, "文件类型不支持"),

    // ── 5xxx 工作流 ─────────────────────────────────────────
    WORKFLOW_NOT_FOUND(5000, "工作流不存在"),
    WORKFLOW_DEPLOY_FAILED(5001, "工作流部署失败"),
    WORKFLOW_START_FAILED(5002, "工作流启动失败"),
    TASK_NOT_FOUND(5003, "任务不存在"),
    TASK_ALREADY_CLAIMED(5004, "任务已被认领"),

    // ── 6xxx 业务规则 ───────────────────────────────────────
    BUSINESS_RULE_VIOLATION(6000, "业务规则校验失败"),
    DUPLICATE_ENTRY(6001, "数据已存在"),
    DATA_INTEGRITY_ERROR(6002, "数据完整性错误"),

    // ── 7xxx 外部系统 ───────────────────────────────────────
    EXTERNAL_SERVICE_ERROR(7000, "外部系统调用失败"),
    EXTERNAL_SERVICE_TIMEOUT(7001, "外部系统调用超时"),
    STORAGE_ERROR(7002, "存储服务异常"),
    MQ_SEND_FAILED(7003, "消息发送失败"),
    ;

    private final int code;
    private final String message;

    ErrorCode(int code, String message) {
        this.code = code;
        this.message = message;
    }
}
