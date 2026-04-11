import { businessClient } from '../../../services/api'
import type { RuleExecuteParams, RuleListQuery, RuleRecord, RuleRemotePage, RuleRemoteResponse } from './types'

async function unwrapRemote<T>(promise: Promise<{ data: RuleRemoteResponse<T> }>) {
  const response = await promise
  return response.data
}

export const ruleApi = {
  listRules(params: RuleListQuery) {
    return unwrapRemote<RuleRemotePage<RuleRecord>>(businessClient.post('/api/v1/rule/ruleList', params))
  },
  getRuleById(id: number | string) {
    return unwrapRemote<RuleRecord>(businessClient.get(`/api/v1/rule/getRuleById/${id}`))
  },
  saveOrUpdateRule(payload: Partial<RuleRecord>) {
    return unwrapRemote<RuleRecord>(businessClient.post('/api/v1/rule/saveOrUpdateRule', payload))
  },
  deleteRule(id: number | string) {
    return unwrapRemote<void>(businessClient.delete(`/api/v1/rule/delete/${id}`))
  },
  enableRule(id: number | string) {
    return unwrapRemote<void>(businessClient.get(`/api/v1/rule/enable/${id}`))
  },
  executeRule(ruleCode: string, version: number | string, params: RuleExecuteParams) {
    return unwrapRemote<unknown>(businessClient.post(`/api/v1/rule/${ruleCode}/${version}`, params))
  },
}
