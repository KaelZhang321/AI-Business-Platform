import { apiClient } from '../api'

type ApiEnvelope<T> = {
  data?: T
}

type PatientExamSessionsQueryInput = {
  mobile?: string
  idCard?: string
  patientName?: string
  [key: string]: unknown
}

type CustomerListQueryInput = {
  pageNo?: number | string
  pageSize?: number | string
  page?: number | string
  size?: number | string
  queryParams?: Record<string, unknown>
  body?: Record<string, unknown>
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
    return response.data?.data ?? response.data
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
