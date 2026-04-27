import { apiClient as client, type ApiResponse } from './client';

export interface RegionLevelCount {
  region: string
  real_identity: string | null
  register_count: number
  arrive_count: number
}

export interface MatrixRow {
  region: string
  qianwan_register: number
  qianwan_arrive: number
  baiwan_register: number
  baiwan_arrive: number
  putong_register: number
  putong_arrive: number
  total_register: number
  total_arrive: number
}

export const fetchRegistrationChart = () =>
  client.get<ApiResponse<RegionLevelCount[]>>('/api/v1/bi/registration/chart').then(r => r.data.data)

export const fetchRegistrationMatrix = () =>
  client.get<ApiResponse<MatrixRow[]>>('/api/v1/bi/registration/matrix').then(r => r.data.data)

export interface RegistrationDetail {
  customer_name: string | null
  sign_in_status: string | null
  customer_category: string | null
  real_identity: string | null
  attendee_role: string | null
  store_name: string | null
  region: string | null
}

export const fetchRegistrationDetail = (region?: string, level?: string) =>
  client.get<ApiResponse<RegistrationDetail[]>>('/api/v1/bi/registration/detail', { params: { region, level } }).then(r => r.data.data)
