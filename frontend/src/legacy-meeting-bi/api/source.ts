import { apiClient as client, type ApiResponse } from './client';

export interface SourceCount {
  region: string
  source_type: string
  customer_count: number
}

export interface TargetArrival {
  region: string
  target_count: number
  arrive_count: number
}

export const fetchSourceDistribution = () =>
  client.get<ApiResponse<SourceCount[]>>('/api/v1/bi/source/distribution').then(r => r.data.data)

export const fetchTargetArrival = () =>
  client.get<ApiResponse<TargetArrival[]>>('/api/v1/bi/source/target-arrival').then(r => r.data.data)

export interface TargetCustomerDetail {
  customer_name: string | null
  region: string | null
  customer_level: string | null
  new_or_old_customer: string | null
  min_deal: number | null
  max_deal: number | null
  prep_maturity: string | null
  is_arrived: boolean
}

export const fetchTargetCustomerDetail = (region?: string) =>
  client.get<ApiResponse<TargetCustomerDetail[]>>('/api/v1/bi/source/target-detail', { params: { region } }).then(r => r.data.data)
