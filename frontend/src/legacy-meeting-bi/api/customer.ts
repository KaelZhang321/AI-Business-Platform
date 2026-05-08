import { apiClient as client, unwrapApiResponse, type ApiResponse } from './client';

export interface PieSlice {
  name: string
  value: number
  percentage: number
}

export interface CustomerProfile {
  level_distribution: PieSlice[]
  role_distribution: PieSlice[]
  new_old_distribution: PieSlice[]
}

export const fetchCustomerProfile = () =>
  client.get<ApiResponse<CustomerProfile>>('/api/v1/bi/customer/profile').then(r => unwrapApiResponse<CustomerProfile>(r.data, {
    level_distribution: [],
    role_distribution: [],
    new_old_distribution: [],
  }))
