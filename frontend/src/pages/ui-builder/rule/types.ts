export interface RuleRemoteResponse<T> {
  success: boolean
  message: string
  data: T
}

export type RuleExecuteParams = Record<string, unknown>

export interface RuleRemotePage<T> {
  records: T[]
  total: number
  size: number
  current: number
  pages: number
}

export interface RuleListQuery {
  pageNo?: number
  pageSize?: number
  id?: string
}

export interface RuleRecord {
  id?: string
  ruleName: string
  ruleCode: string
  description?: string
  version?: string
  status?: string
  createdBy?: string
  nodeDetail?: string
  createdTime?: string
  updatedBy?: string
  updatedTime?: string
  ruleNodes?: RuleNodeRecord[]
}

export interface RuleDataSourceOption {
  key: string
  label: string
  defaultSelected: boolean
}

export interface RuleNodeRecord {
  id?: string
  ruleId?: string
  nodeName?: string
  nodeType?: string
  nodeGroup?: string
  nodeSql?: string
  sortOrder?: number
  nodeConfig?: string
  ruleVersion?: string
}

export type RuleCanvasNodeType = 'input' | 'sql' | 'parse' | 'calculate' | 'output' | 'http'

export interface RuleCanvasNode {
  id: string
  type: RuleCanvasNodeType
  position?: {
    x: number
    y: number
  }
  data: {
    label: string
    params: RuleNodeParams
  }
}

export interface RuleCanvasEdge {
  id: string
  source: string
  target: string
  type?: string
  markerEnd?: {
    type: string
    color: string
  }
}

export interface RuleValidationRule {
  paramName: string
  type: 'NULL' | 'NOT_NULL' | 'REGEX' | 'RANGE'
  value?: string
}

export interface RuleHttpParam {
  sourceParam: string
  paramType: 'query' | 'header' | 'body'
  targetKey: string
}

export interface RuleNodeParams {
  label: string
  nodeType: string
  nodeGroup: number
  nodeSql?: string
  nodeConfig: Record<string, unknown>
}

export interface RuleEditorNodeFormValues {
  label: string
  nodeGroup: number
  validationRules: RuleValidationRule[]
  nodeSql?: string
  dataSourceKey?: string
  resultKey?: string
  resultType?: string
  sourceKey?: string
  targetKey?: string
  parseType?: string
  columnName?: string
  filterColumnName?: string
  filterOperator?: string
  filterValue?: string
  operation?: string
  expression?: string
  variables?: string
  outputType?: string
  format?: string
  target?: string
  httpMethod?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  url?: string
  timeout?: number
  httpParams: RuleHttpParam[]
}
