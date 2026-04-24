import client, { type ApiResponse } from './client'

export interface AchievementBar {
  region: string
  low_limit: number
  high_limit: number
  deal_amount: number
}

export interface AchievementRow {
  row_num: number
  region: string
  actual_amount: number
  target_amount: number
  min_limit: number
  max_limit: number
  achievement_rate: number | null
  difference: number
}

export const fetchAchievementChart = () =>
  client.get<ApiResponse<AchievementBar[]>>('/v1/achievement/chart').then(r => r.data.data)

export const fetchAchievementTable = () =>
  client.get<ApiResponse<AchievementRow[]>>('/v1/achievement/table').then(r => r.data.data)

export interface AchievementDetail {
  customer_name: string | null
  region: string | null
  branch: string | null
  deal_type: string | null
  deal_content: string | null
  new_deal_amount: number
  received_amount: number
  plan_type: string | null
  record_date: string | null
}

export const fetchAchievementDetail = (region?: string) =>
  client.get<ApiResponse<AchievementDetail[]>>('/v1/achievement/detail', { params: { region } }).then(r => r.data.data)
