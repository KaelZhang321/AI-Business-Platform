/**
 * 统一 AI Query 客户端
 *
 * 封装 /api/v1/api-query 请求，标准化 context 传递和响应解析。
 * 所有 AI 相关页面应使用此客户端而非直接调用 apiClient。
 */
import { apiClient } from '../api';
import type { AiQueryRequest, AiQueryResponse, AiQueryContext } from '../../types/aiQuery';

const AI_QUERY_ENDPOINT = '/api/v1/api-query';

/**
 * 发送 AI 查询请求
 *
 * @param request - AI 查询请求参数
 * @returns AI 查询响应
 */
export async function query(request: AiQueryRequest): Promise<AiQueryResponse> {
  const payload = {
    query: request.query,
    conversation_id: request.conversationId,
    ...(request.context && { context: request.context }),
    ...(request.interactionId && { interaction_id: request.interactionId }),
  };

  const response = await apiClient.post<AiQueryResponse>(AI_QUERY_ENDPOINT, payload);
  return response.data;
}

/**
 * 构建标准化的页面上下文
 *
 * @param page - 页面标识
 * @param overrides - 额外上下文字段
 * @returns AiQueryContext
 */
export function buildContext(
  page: string,
  overrides?: Partial<Omit<AiQueryContext, 'page'>>,
): AiQueryContext {
  return {
    page,
    ...overrides,
  };
}

/**
 * 判断响应是否需要澄清
 */
export function needsClarification(response: AiQueryResponse): boolean {
  return response.execution_status === 'WAIT_CLARIFY';
}

/**
 * 判断响应是否成功
 */
export function isSuccess(response: AiQueryResponse): boolean {
  return response.execution_status === 'SUCCESS';
}

export const aiQueryApi = {
  query,
  buildContext,
  needsClarification,
  isSuccess,
};

export default aiQueryApi;
