import { apiClient } from '../api'
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
}
