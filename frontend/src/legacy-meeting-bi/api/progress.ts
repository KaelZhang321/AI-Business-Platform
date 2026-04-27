import { apiClient as client, type ApiResponse } from './client';

export interface ProgressItem {
  region: string
  deal_amount: number
  high_limit: number
  completion_rate: number | null
}

export interface ProgressSummary {
  items: ProgressItem[]
  avg_completion_rate: number | null
}

export const fetchProgress = () =>
  client.get<ApiResponse<ProgressSummary>>('/api/v1/bi/progress/ranking').then(r => r.data.data)
