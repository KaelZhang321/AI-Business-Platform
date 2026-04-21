import { apiClient } from '../api'

type ApiEnvelope<T> = {
  data?: T
}

export type HealthQuadrantRequest = {
  sex: string
  age: number
  study_id: string
  single_exam_items: string[]
  chief_complaint_text: string
  quadrant_type?: string
}

export type HealthQuadrantItem = {
  q_code?: string
  q_name?: string
  abnormal_indicators?: string[]
  recommendation_plans?: string[]
}

export type HealthQuadrantResponse = {
  quadrants?: HealthQuadrantItem[]
}

/**
 * AI 报告页相关接口
 */
export const aIFourQuadrantViewApi = {
  /**
   * 四象限健康评估
   * POST /api/v1/health-quadrant
   */
  async getHealthQuadrantAnalysisApi(params: HealthQuadrantRequest) {
    const response = await apiClient.post<ApiEnvelope<HealthQuadrantResponse>>('/api/v1/health-quadrant', params)
    return response.data?.data ?? response.data
  },
}
