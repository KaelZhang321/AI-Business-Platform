import { apiClient } from '../api'

/** 后端统一响应包装 */
type ApiEnvelope<T> = {
  /** 业务数据 */
  data?: T
}

/** 四象限健康评估 —— 请求参数 */
export type HealthQuadrantRequest = {
  /** 患者性别 */
  sex: string
  /** 患者年龄 */
  age: number
  /** 体检记录 ID */
  study_id: string
  /** 单项体检项目列表 */
  single_exam_items: string[]
  /** 主诉文本 */
  chief_complaint_text: string
  /** 象限类型（可选） */
  quadrant_type?: string
}

/** 四象限评估结果单项 */
export type HealthQuadrantItem = {
  /** 象限编码 */
  q_code?: string
  /** 象限名称 */
  q_name?: string
  /** 异常指标列表 */
  abnormal_indicators?: string[]
  /** 建议方案列表 */
  recommendation_plans?: string[]
}

/** 四象限评估 —— 响应数据 */
export type HealthQuadrantResponse = {
  /** 四个象限的评估结果列表 */
  quadrants?: HealthQuadrantItem[]
}

/** 四象限结果确认单项（用户编辑后提交） */
export type HealthQuadrantConfirmItem = {
  /** 象限编码 */
  q_code: string
  /** 象限名称 */
  q_name?: string
  /** 确认后的异常指标 */
  abnormalIndicators: string[]
  /** 确认后的建议方案 */
  recommendationPlans: string[]
}

/** 四象限结果确认 —— 请求参数 */
export type HealthQuadrantConfirmRequest = {
  /** 患者性别 */
  sex: string
  /** 患者年龄 */
  age: number
  /** 体检记录 ID */
  study_id: string
  /** 象限类型 */
  quadrant_type: string
  /** 主诉文本 */
  chief_complaint_text: string
  /** 确认后的四象限结果列表 */
  quadrants: HealthQuadrantConfirmItem[]
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

  /**
   * 四象限结果确认
   * POST /api/v1/health-quadrant/confirm
   */
  async confirmHealthQuadrantApi(params: HealthQuadrantConfirmRequest) {
    const response = await apiClient.post<ApiEnvelope<unknown>>('/api/v1/health-quadrant/confirm', params)
    return response.data?.data ?? response.data
  },
}
