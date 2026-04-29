/**
 * AI Query 统一类型定义
 *
 * 标准化前端与 ai-gateway /api/v1/api-query 的请求/响应契约。
 */

/** 页面上下文 — 帮助后端 FastIntentRouter 做精准意图识别 */
export interface AiQueryContext {
    /** 当前页面标识 */
    page: string;
    /** 当前模块标识 */
    module?: string;
    /** 当前选中的业务实体 */
    selectedEntity?: Record<string, unknown>;
    /** 当前可见的卡片/面板 ID 列表 */
    visibleCards?: string[];
    /** 当前可用的操作列表 */
    availableActions?: string[];
    /** 会话 ID（多轮对话） */
    conversationId?: string;
    /** 上一次识别的意图 */
    lastIntent?: string;
    /** 扩展字段 */
    extra?: Record<string, unknown>;
}

/** AI Query 请求参数 */
export interface AiQueryRequest {
    /** 用户自然语言输入 */
    query: string;
    /** 页面上下文 */
    context?: AiQueryContext;
    /** 会话 ID */
    conversationId?: string;
    /** 交互 ID（单次请求唯一标识） */
    interactionId?: string;
}

/** AI Query 执行状态 */
export type AiQueryExecutionStatus =
    | 'SUCCESS'
    | 'EMPTY'
    | 'ERROR'
    | 'SKIPPED'
    | 'PARTIAL_SUCCESS'
    | 'WAIT_CLARIFY';

/** 澄清选项 */
export interface AiQueryClarifyOption {
    label: string;
    query_domains: string[];
    business_intents?: string[];
}

/** AI Query 响应 */
export interface AiQueryResponse {
    /** 链路追踪 ID */
    trace_id: string;
    /** 执行状态 */
    execution_status: AiQueryExecutionStatus;
    /** 执行计划 */
    execution_plan?: {
        plan_id: string;
        steps: Array<{
            step_id: string;
            api_path: string;
            params: Record<string, unknown>;
        }>;
    };
    /** UI 渲染规格 */
    ui_spec?: Record<string, unknown>;
    /** 错误信息 */
    error?: string;
    /** 澄清消息（WAIT_CLARIFY 状态时） */
    message?: string;
    /** 澄清选项（WAIT_CLARIFY 状态时） */
    options?: AiQueryClarifyOption[];
}

/** AI 请求阶段状态（前端状态机） */
export type AiRequestStage =
    | 'idle'
    | 'routing'
    | 'retrieving'
    | 'executing'
    | 'rendering'
    | 'clarifying'
    | 'done'
    | 'error';