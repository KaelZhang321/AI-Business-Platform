import { apiClient as client, type ApiResponse } from './client';

export interface ProposalRow {
  proposal_type: string
  sub_proposal_type: string | null
  target_count: number
  actual_count: number
  target_amount: number
  actual_amount: number
}

export interface ProposalCrossRow {
  region: string
  proposals: Record<string, number>
}

export const fetchProposalOverview = () =>
  client.get<ApiResponse<ProposalRow[]>>('/api/v1/bi/proposal/overview').then(r => r.data.data)

export const fetchProposalCrossTable = () =>
  client.get<ApiResponse<ProposalCrossRow[]>>('/api/v1/bi/proposal/cross-table').then(r => r.data.data)

export interface ProposalDetailRow {
  customer_name: string | null
  region: string | null
  deal_content: string | null
  new_deal_amount: number
  received_amount: number
  record_date: string | null
}

export const fetchProposalDetail = (region?: string, proposal_type?: string) =>
  client.get<ApiResponse<ProposalDetailRow[]>>('/api/v1/bi/proposal/detail', { params: { region, proposal_type } }).then(r => r.data.data)
