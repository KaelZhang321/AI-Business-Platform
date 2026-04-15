export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PageQuery {
  page?: number
  size?: number
}

export interface PageResult<T> {
  data: T[]
  total: number
  page: number
  size: number
}

export interface RemoteResponse<T> {
  success: boolean
  message: string
  data: T
}

export interface RemotePageResult<T> {
  records: T[]
  total: number
  size: number
  current: number
  pages: number
}

export interface UiBuilderFeature {
  title: string
  description: string
}

export interface UiBuilderField {
  name: string
  type: string
  description: string
}

export interface UiBuilderTableSchema {
  name: string
  purpose: string
  fields: UiBuilderField[]
}

export interface UiBuilderNodeType {
  type: string
  description: string
  supportsChildren: boolean
  keyProps: string[]
}

export interface UiBuilderAuthType {
  type: string
  description: string
}

export interface UiBuilderOverview {
  moduleName: string
  description: string
  features: UiBuilderFeature[]
  workflowSteps: string[]
  authTypes: UiBuilderAuthType[]
  nodeTypes: UiBuilderNodeType[]
  tables: UiBuilderTableSchema[]
}

export interface SemanticFieldDict {
  id: number
  standardKey: string
  label: string
  fieldType: string
  category?: string | null
  valueMap?: string | null
  description?: string | null
  isActive?: number | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface SemanticFieldAlias {
  id: number
  standardKey: string
  alias: string
  apiId: string
  source?: string | null
  createdAt?: string | null
}

export interface SemanticFieldValueMap {
  id: number
  standardKey: string
  apiId?: string | null
  standardValue: string
  rawValue: string
  sortOrder?: number | null
}

export interface UiApiSource {
  id: string
  name: string
  code: string
  description?: string | null
  sourceType: string
  baseUrl?: string | null
  docUrl?: string | null
  authType: string
  authConfig?: string | null
  defaultHeaders?: string | null
  env?: string | null
  status?: string | null
  createdBy?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface UiApiEndpoint {
  id: string
  sourceId: string
  tagId?: string | null
  tagName?: string | null
  name: string
  path: string
  method: string
  operationSafety?: 'query' | 'list' | 'mutation' | null
  summary?: string | null
  requestContentType?: string | null
  requestSchema?: string | null
  responseSchema?: string | null
  sampleRequest?: string | null
  sampleResponse?: string | null
  fieldOrchestration?: string | null
  status?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface UiRole {
  id: string
  appCode?: string | null
  roleName: string
  roleCode?: string | null
  roleDesc?: string | null
  status?: number | null
  createTime?: string | null
  updateTime?: string | null
}

export interface UiApiEndpointRole {
  id: string
  endpointId: string
  roleId: string
  roleCode?: string | null
  roleName: string
  fieldOrchestration?: string | null
  createdBy?: string | null
  createdAt?: string | null
  updatedAt?: string | null
  endpointName?: string | null
  endpointPath?: string | null
  endpointMethod?: string | null
  endpointStatus?: string | null
  sourceId?: string | null
  sourceName?: string | null
  tagName?: string | null
}

export interface UiApiTestLog {
  id: string
  endpointId: string
  requestUrl: string
  requestHeaders?: string | null
  requestQuery?: string | null
  requestBody?: string | null
  responseStatus?: number | null
  responseHeaders?: string | null
  responseBody?: string | null
  successFlag: number
  errorMessage?: string | null
  createdBy?: string | null
  createdAt?: string | null
}

export interface UiApiFlowLog {
  id: string
  flowNum?: string | null
  endpointId?: string | null
  requestUrl?: string | null
  requestHeaders?: string | null
  requestQuery?: string | null
  requestBody?: string | null
  responseStatus?: number | null
  responseHeaders?: string | null
  responseBody?: string | null
  invokeStatus?: string | null
  errorMessage?: string | null
  createdBy?: string | null
  createdByName?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface UiApiTag {
  id: string
  sourceId: string
  name: string
  code: string
  description?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface UiApiTestResponse {
  requestUrl: string
  responseStatus?: number | null
  responseHeaders: Record<string, unknown>
  responseBody: unknown
  success: boolean
  errorMessage?: string | null
}

export interface UiApiInvokeRequest {
  flowNum?: string
  headers?: Record<string, unknown>
  queryParams?: Record<string, unknown>
  body?: unknown
  createdBy?: string
  createdByName?: string
  useSampleWhenEmpty?: boolean
}

export interface UiJsonRenderInvokeRequest extends UiApiInvokeRequest {
  roleId?: string
}

export interface UiJsonRenderInvokeResponse {
  endpointId: string
  roleId?: string | null
  flowNum?: string | null
  flowLogId?: string | null
  responseBody: unknown
  jsonRender: Record<string, unknown>
}

export interface UiJsonRenderSubmitActionRequest {
  endpointId: string
  roleId?: string
  queryKeys?: string[]
  bodyKeys?: string[]
  headerKeys?: string[]
  staticQueryParams?: Record<string, unknown>
  staticBody?: Record<string, unknown>
  staticHeaders?: Record<string, unknown>
  useSampleWhenEmpty?: boolean
}

export interface UiJsonRenderSubmitRequest {
  flowNum?: string
  createdBy?: string
  createdByName?: string
  semanticValues: Record<string, unknown>
  actions: UiJsonRenderSubmitActionRequest[]
}

export interface UiJsonRenderSubmitActionResponse {
  endpointId: string
  endpointName?: string | null
  flowLogId?: string | null
  requestUrl?: string | null
  success: boolean
  errorMessage?: string | null
  responseStatus?: number | null
  responseBody?: unknown
}

export interface UiJsonRenderSubmitResponse {
  flowNum?: string | null
  success: boolean
  results: UiJsonRenderSubmitActionResponse[]
}

export interface UiProject {
  id: string
  name: string
  code: string
  description?: string | null
  category?: string | null
  status?: string | null
  createdBy?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface UiPage {
  id: string
  projectId: string
  name: string
  code: string
  title?: string | null
  routePath?: string | null
  rootNodeId?: string | null
  layoutType?: string | null
  status?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface UiPageNode {
  id: string
  pageId: string
  parentId?: string | null
  nodeKey: string
  nodeType: string
  nodeName: string
  sortOrder?: number | null
  slotName?: string | null
  propsConfig?: string | null
  styleConfig?: string | null
  status?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface UiNodeBinding {
  id: string
  nodeId: string
  endpointId?: string | null
  bindingType: string
  targetProp: string
  sourcePath?: string | null
  transformScript?: string | null
  defaultValue?: string | null
  requiredFlag?: boolean | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface UiSpecVersion {
  id: string
  projectId: string
  pageId: string
  versionNo: number
  publishStatus: string
  specContent: string
  sourceSnapshot?: string | null
  publishedBy?: string | null
  publishedAt?: string | null
  createdAt?: string | null
}

export interface UiBuilderPageDetail {
  page: UiPage
  nodes: UiPageNode[]
  bindings: UiNodeBinding[]
}

export interface UiPagePreviewResponse {
  pageId: string
  rootNodeId?: string | null
  spec: Record<string, unknown>
}

export interface UiApiSourceRequest {
  name: string
  code: string
  description?: string
  sourceType: string
  baseUrl?: string
  docUrl?: string
  authType: string
  authConfig?: string
  defaultHeaders?: string
  env?: string
  status?: string
  createdBy?: string
}

export interface UiApiEndpointRequest {
  sourceId: string
  tagId?: string
  name: string
  path: string
  method: string
  operationSafety?: 'query' | 'list' | 'mutation'
  summary?: string
  requestContentType?: string
  requestSchema?: string
  responseSchema?: string
  sampleRequest?: string
  sampleResponse?: string
  fieldOrchestration?: string
  status?: string
}

export interface UiApiTestRequest {
  headers?: Record<string, unknown>
  queryParams?: Record<string, unknown>
  body?: unknown
  createdBy?: string
}

export interface SemanticFieldDictRequest {
  standardKey: string
  label: string
  fieldType: string
  category?: string
  valueMap?: string
  description?: string
  isActive?: number
}

export interface SemanticFieldAliasRequest {
  standardKey: string
  alias: string
  apiId: string
  source?: string
}

export interface SemanticFieldValueMapRequest {
  standardKey: string
  apiId?: string
  standardValue: string
  rawValue: string
  sortOrder?: number
}

export interface UiApiEndpointRoleBindRequest {
  roleId: string
  roleCode?: string
  roleName: string
  endpointIds: string[]
  createdBy?: string
}

export interface UiProjectRequest {
  name: string
  code: string
  description?: string
  category?: string
  status?: string
  createdBy?: string
}

export interface UiPageRequest {
  name: string
  code: string
  title?: string
  routePath?: string
  rootNodeId?: string
  layoutType?: string
  status?: string
}

export interface UiPageNodeRequest {
  parentId?: string
  nodeKey: string
  nodeType: string
  nodeName: string
  sortOrder?: number
  slotName?: string
  propsConfig?: string
  styleConfig?: string
  status?: string
}

export interface UiNodeBindingRequest {
  endpointId?: string
  bindingType: string
  targetProp: string
  sourcePath?: string
  transformScript?: string
  defaultValue?: string
  requiredFlag?: boolean
}

export interface UiOpenApiImportPayload {
  document?: string
  documentUrl?: string
}
