"""
统一错误码常量 — 与 Java 业务编排层 ErrorCode 码段对齐。

码段划分：
  1xxx — 通用错误
  2xxx — 认证/授权
  3xxx — AI 服务
  4xxx — 知识库
  5xxx — 工作流
  6xxx — 业务规则
  7xxx — 外部系统
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class ErrorCode:
    code: int
    message: str

    # ── 1xxx 通用 ────────────────────────────────────────────
    SUCCESS: ClassVar[ErrorCode]
    BAD_REQUEST: ClassVar[ErrorCode]
    VALIDATION_FAILED: ClassVar[ErrorCode]
    RESOURCE_NOT_FOUND: ClassVar[ErrorCode]
    RATE_LIMITED: ClassVar[ErrorCode]
    INTERNAL_ERROR: ClassVar[ErrorCode]

    # ── 2xxx 认证/授权 ──────────────────────────────────────
    UNAUTHORIZED: ClassVar[ErrorCode]
    TOKEN_EXPIRED: ClassVar[ErrorCode]
    TOKEN_INVALID: ClassVar[ErrorCode]

    # ── 3xxx AI 服务 ────────────────────────────────────────
    AI_SERVICE_UNAVAILABLE: ClassVar[ErrorCode]
    MODEL_NOT_FOUND: ClassVar[ErrorCode]
    LLM_CALL_FAILED: ClassVar[ErrorCode]
    INTENT_CLASSIFY_FAILED: ClassVar[ErrorCode]
    TEXT2SQL_FAILED: ClassVar[ErrorCode]
    TEXT2SQL_UNSAFE: ClassVar[ErrorCode]

    # ── 4xxx 知识库 ─────────────────────────────────────────
    KNOWLEDGE_BASE_NOT_FOUND: ClassVar[ErrorCode]
    DOCUMENT_NOT_FOUND: ClassVar[ErrorCode]
    RAG_SEARCH_FAILED: ClassVar[ErrorCode]

    # ── 7xxx 外部系统 ───────────────────────────────────────
    EXTERNAL_SERVICE_ERROR: ClassVar[ErrorCode]
    EXTERNAL_SERVICE_TIMEOUT: ClassVar[ErrorCode]


# 初始化 ClassVar 值
ErrorCode.SUCCESS = ErrorCode(0, "success")
ErrorCode.BAD_REQUEST = ErrorCode(1000, "请求参数错误")
ErrorCode.VALIDATION_FAILED = ErrorCode(1001, "参数校验失败")
ErrorCode.RESOURCE_NOT_FOUND = ErrorCode(1002, "资源不存在")
ErrorCode.RATE_LIMITED = ErrorCode(1004, "请求过于频繁")
ErrorCode.INTERNAL_ERROR = ErrorCode(1999, "系统内部错误")

ErrorCode.UNAUTHORIZED = ErrorCode(2000, "未认证")
ErrorCode.TOKEN_EXPIRED = ErrorCode(2001, "Token 已过期")
ErrorCode.TOKEN_INVALID = ErrorCode(2002, "Token 无效")

ErrorCode.AI_SERVICE_UNAVAILABLE = ErrorCode(3000, "AI 服务不可用")
ErrorCode.MODEL_NOT_FOUND = ErrorCode(3001, "模型不存在")
ErrorCode.LLM_CALL_FAILED = ErrorCode(3002, "LLM 调用失败")
ErrorCode.INTENT_CLASSIFY_FAILED = ErrorCode(3003, "意图分类失败")
ErrorCode.TEXT2SQL_FAILED = ErrorCode(3004, "Text2SQL 执行失败")
ErrorCode.TEXT2SQL_UNSAFE = ErrorCode(3005, "SQL 安全检查未通过")

ErrorCode.KNOWLEDGE_BASE_NOT_FOUND = ErrorCode(4000, "知识库不存在")
ErrorCode.DOCUMENT_NOT_FOUND = ErrorCode(4001, "文档不存在")
ErrorCode.RAG_SEARCH_FAILED = ErrorCode(4004, "知识检索失败")

ErrorCode.EXTERNAL_SERVICE_ERROR = ErrorCode(7000, "外部系统调用失败")
ErrorCode.EXTERNAL_SERVICE_TIMEOUT = ErrorCode(7001, "外部系统调用超时")


class BusinessError(Exception):
    """业务异常 — 携带统一错误码，由 FastAPI exception_handler 统一捕获。"""

    def __init__(self, error_code: ErrorCode, detail: str | None = None) -> None:
        self.error_code = error_code
        self.detail = detail or error_code.message
        super().__init__(self.detail)

    @property
    def code(self) -> int:
        return self.error_code.code
