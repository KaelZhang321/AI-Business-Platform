package com.lzke.ai.exception;

import com.lzke.ai.interfaces.dto.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.stream.Collectors;

/**
 * 全局异常处理器 — 统一将异常转为 ApiResponse 格式返回。
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    // ── 业务异常 ─────────────────────────────────────────────
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusinessException(BusinessException ex, HttpServletRequest request) {
        log.warn("业务异常 [{}] {}: {}", ex.getCode(), request.getRequestURI(), ex.getMessage());
        return ResponseEntity
                .status(mapHttpStatus(ex.getErrorCode()))
                .body(ApiResponse.error(ex.getCode(), ex.getMessage()));
    }

    // ── Spring ResponseStatusException 兼容（渐进迁移期保留）───
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<ApiResponse<Void>> handleResponseStatusException(ResponseStatusException ex) {
        int code = mapErrorCode(ex.getStatusCode().value());
        log.warn("ResponseStatusException [{}]: {}", ex.getStatusCode(), ex.getReason());
        return ResponseEntity
                .status(ex.getStatusCode())
                .body(ApiResponse.error(code, ex.getReason()));
    }

    // ── 参数校验失败 ─────────────────────────────────────────
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidation(MethodArgumentNotValidException ex) {
        String detail = ex.getBindingResult().getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining("; "));
        log.warn("参数校验失败: {}", detail);
        return ResponseEntity
                .badRequest()
                .body(ApiResponse.error(ErrorCode.VALIDATION_FAILED.getCode(), detail));
    }

    // ── 缺少请求参数 ─────────────────────────────────────────
    @ExceptionHandler(MissingServletRequestParameterException.class)
    public ResponseEntity<ApiResponse<Void>> handleMissingParam(MissingServletRequestParameterException ex) {
        log.warn("缺少请求参数: {}", ex.getParameterName());
        return ResponseEntity
                .badRequest()
                .body(ApiResponse.error(ErrorCode.BAD_REQUEST.getCode(), "缺少参数: " + ex.getParameterName()));
    }

    // ── 请求体解析失败 ───────────────────────────────────────
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiResponse<Void>> handleUnreadable(HttpMessageNotReadableException ex) {
        log.warn("请求体解析失败: {}", ex.getMessage());
        return ResponseEntity
                .badRequest()
                .body(ApiResponse.error(ErrorCode.BAD_REQUEST.getCode(), "请求体格式错误"));
    }

    // ── 请求方法不支持 ───────────────────────────────────────
    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<ApiResponse<Void>> handleMethodNotAllowed(HttpRequestMethodNotSupportedException ex) {
        return ResponseEntity
                .status(HttpStatus.METHOD_NOT_ALLOWED)
                .body(ApiResponse.error(ErrorCode.METHOD_NOT_ALLOWED.getCode(), ex.getMessage()));
    }

    // ── 上传文件过大 ─────────────────────────────────────────
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<ApiResponse<Void>> handleMaxUploadSize(MaxUploadSizeExceededException ex) {
        log.warn("文件上传过大: {}", ex.getMessage());
        return ResponseEntity
                .status(HttpStatus.PAYLOAD_TOO_LARGE)
                .body(ApiResponse.error(ErrorCode.DOCUMENT_UPLOAD_FAILED.getCode(), "文件大小超出限制"));
    }

    // ── 404 资源不存在 ───────────────────────────────────────
    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleNoResource(NoResourceFoundException ex) {
        return ResponseEntity
                .status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.error(ErrorCode.RESOURCE_NOT_FOUND.getCode(), "资源不存在: " + ex.getResourcePath()));
    }

    // ── 兜底异常 ─────────────────────────────────────────────
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleUnknown(Exception ex, HttpServletRequest request) {
        log.error("未处理异常 {}: {}", request.getRequestURI(), ex.getMessage(), ex);
        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.error(ErrorCode.INTERNAL_ERROR.getCode(), "系统内部错误，请稍后重试"));
    }

    // ── 辅助方法 ─────────────────────────────────────────────

    /**
     * ErrorCode → HTTP 状态码映射
     */
    private HttpStatus mapHttpStatus(ErrorCode errorCode) {
        return switch (errorCode) {
            case UNAUTHORIZED, TOKEN_EXPIRED, TOKEN_INVALID,
                 REFRESH_TOKEN_INVALID, ACCOUNT_NOT_FOUND, PASSWORD_INCORRECT -> HttpStatus.UNAUTHORIZED;
            case ACCOUNT_DISABLED, PERMISSION_DENIED -> HttpStatus.FORBIDDEN;
            case RESOURCE_NOT_FOUND, KNOWLEDGE_BASE_NOT_FOUND, DOCUMENT_NOT_FOUND,
                 WORKFLOW_NOT_FOUND, TASK_NOT_FOUND, MODEL_NOT_FOUND -> HttpStatus.NOT_FOUND;
            case BAD_REQUEST, VALIDATION_FAILED -> HttpStatus.BAD_REQUEST;
            case METHOD_NOT_ALLOWED -> HttpStatus.METHOD_NOT_ALLOWED;
            case RATE_LIMITED -> HttpStatus.TOO_MANY_REQUESTS;
            case DUPLICATE_ENTRY, TASK_ALREADY_CLAIMED -> HttpStatus.CONFLICT;
            default -> HttpStatus.INTERNAL_SERVER_ERROR;
        };
    }

    /**
     * HTTP 状态码 → 错误码映射（兼容 ResponseStatusException）
     */
    private int mapErrorCode(int httpStatus) {
        return switch (httpStatus) {
            case 400 -> ErrorCode.BAD_REQUEST.getCode();
            case 401 -> ErrorCode.UNAUTHORIZED.getCode();
            case 403 -> ErrorCode.PERMISSION_DENIED.getCode();
            case 404 -> ErrorCode.RESOURCE_NOT_FOUND.getCode();
            case 405 -> ErrorCode.METHOD_NOT_ALLOWED.getCode();
            case 429 -> ErrorCode.RATE_LIMITED.getCode();
            default -> ErrorCode.INTERNAL_ERROR.getCode();
        };
    }
}
