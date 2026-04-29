import { apiClient } from '../api'
import { aiQueryApi } from './aiQueryApi'
import type { AiQueryResponse } from '../../types/aiQuery'
import type { PatientExamCleanedResultResponse } from '../../types/patientExamCleanedResult'

/** 后端统一响应包装 */
type ApiEnvelope<T> = {
  /** 业务数据 */
  data?: {
    data?: T
    total?: number
  }
}

/** 体检记录查询参数 */
type PatientExamSessionsQueryInput = {
  /** 手机号（可选） */
  mobile?: string
  /** 身份证号（可选） */
  idCard?: string
  /** 患者姓名（可选） */
  patientName?: string
  [key: string]: unknown
}

/** 客户列表查询参数 */
type CustomerListQueryInput = {
  /** 页码 */
  pageNo?: number | string
  /** 每页条数 */
  pageSize?: number | string
  /** 页码（别名） */
  page?: number | string
  /** 每页条数（别名） */
  size?: number | string
  /** 自定义查询参数 */
  queryParams?: Record<string, unknown>
  /** 请求体 */
  body?: Record<string, unknown>
  /** 客户信息关键词 */
  customerInfo?: string
  [key: string]: unknown
}

/** 客户总览统计 */
export type PatientExamStats = {
  /** 近三年客户总数 */
  recentThreeYearsPatientCount?: number | string | null
  /** 本周新增客户数 */
  thisWeekPatientCount?: number | string | null
  /** 上周新增客户数 */
  lastWeekPatientCount?: number | string | null
}

/** 指标对比页 AI 咨询请求参数 */
export type ComparisonChatQueryInput = {
  /** 用户问题 */
  query: string
  /** 前端透传给后端的上下文 */
  context?: unknown
  /** 允许命中的页面/组件标识 */
  targetIds?: string[]
}

/**
 * AI 报告页相关接口
 */
export const aiReportApi = {
  /**
   * 获取多个体检列表
   * POST /bs/api/v1/patient-exams/results/batch-query
   */
  async getPatientExamListApi(params: any) {
    const response = await apiClient.post<ApiEnvelope<unknown[]>>('/bs/api/v1/patient-exams/results/batch-query', params)
    return response.data?.data ?? response.data
  },
  /**
   * 查询体检记录
   * POST /bs/api/v1/patient-exams/sessions/query
   */
  async getPatientExamSessionsApi(params: PatientExamSessionsQueryInput) {
    const response = await apiClient.post<ApiEnvelope<unknown[]>>('/bs/api/v1/patient-exams/sessions/query', params)
    return response.data?.data?.data ?? response.data?.data ?? response.data
  },
  /**
   * 获取单次体检清洗结果
   * GET /bs/api/v1/patient-exams/{studyId}/cleaned-result
   */
  async getPatientExamCleanedResultApi(studyId: string) {
    const response = await apiClient.get<PatientExamCleanedResultResponse>(`/bs/api/v1/patient-exams/${studyId}/cleaned-result`)
    return response.data
  },
  /**
   * 获取客户列表
   * POST /bs/api/v1/patient-exams/my-customers/query
   */
  async getcustomersListApi(params: CustomerListQueryInput = {}) {
    const response = await apiClient.post<ApiEnvelope<unknown[]>>('/bs/api/v1/patient-exams/my-customers/query', params)
    return response.data?.data ?? response.data
  },
  /**
   * 获取客户统计数据
   * GET /bs/api/v1/patient-exams/stats
   */
  async getPatientExamStatsApi() {
    const response = await apiClient.get<ApiEnvelope<PatientExamStats>>('/bs/api/v1/patient-exams/stats')
    return response.data?.data?.data ?? response.data?.data ?? response.data
  },
  /**
   * 指标对比页 AI 实时咨询
   * POST /api/v1/api-query
   */
  async getComparisonChatRouteApi(params: ComparisonChatQueryInput) {
    return aiQueryApi.query({
      query: params.query,
      context: params.context as Record<string, unknown> | undefined,
    }) as Promise<AiQueryResponse>
  },
}
