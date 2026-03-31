import client, { type ApiResponse } from './client'

export interface OperationsKpi {
  checkin_count: number
  pickup_count: number
  leave_count: number
  hospital_count: number
}

export interface TrendPoint {
  schedule_date: string
  day_time_period: string
  scene_label: string
  people_count: number
}

export const fetchOperationsKpi = (dateFrom?: string, dateTo?: string) =>
  client.get<ApiResponse<OperationsKpi>>('/v1/operations/kpi', {
    params: { date_from: dateFrom, date_to: dateTo },
  }).then(r => r.data.data)

export const fetchTrendData = () =>
  client.get<ApiResponse<TrendPoint[]>>('/v1/operations/trend').then(r => r.data.data)
