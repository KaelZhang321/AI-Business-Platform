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
  summary?: string | null
  requestContentType?: string | null
  requestSchema?: string | null
  responseSchema?: string | null
  sampleRequest?: string | null
  sampleResponse?: string | null
  status?: string | null
  createdAt?: string | null
  updatedAt?: string | null
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
  summary?: string
  requestContentType?: string
  requestSchema?: string
  responseSchema?: string
  sampleRequest?: string
  sampleResponse?: string
  status?: string
}

export interface UiApiTestRequest {
  headers?: Record<string, unknown>
  queryParams?: Record<string, unknown>
  body?: unknown
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
