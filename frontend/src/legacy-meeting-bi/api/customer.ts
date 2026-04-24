import client, { type ApiResponse } from './client'

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
  client.get<ApiResponse<CustomerProfile>>('/v1/customer/profile').then(r => r.data.data)
