import { apiClient as client, type ApiResponse } from './client';

export interface KpiItem {
  label: string
  value: number
  unit: string
  prefix: string
}

export interface KpiOverview {
  registered_customers: KpiItem
  arrived_customers: KpiItem
  deal_amount: KpiItem
  consumed_budget: KpiItem
  received_amount: KpiItem
  roi: KpiItem
}

export const fetchKpiOverview = () =>
  client.get<ApiResponse<KpiOverview>>('/api/v1/bi/kpi/overview').then(r => r.data.data)
