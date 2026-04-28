import { businessClient } from '../../services/api'
import type {
  ApiResponse,
  PageQuery,
  PageResult,
  RemotePageResult,
  RemoteResponse,
  SemanticFieldAlias,
  SemanticFieldAliasRequest,
  SemanticFieldDict,
  SemanticFieldDictRequest,
  SemanticFieldValueMap,
  SemanticFieldValueMapRequest,
  UiApiEndpoint,
  UiApiEndpointRequest,
  UiApiEndpointRole,
  UiApiEndpointRoleBindRequest,
  UiApiFlowLog,
  UiApiInvokeRequest,
  UiCard,
  UiCardEndpointBindRequest,
  UiCardEndpointRelation,
  UiCardRequest,
  UiJsonRenderInvokeRequest,
  UiJsonRenderInvokeResponse,
  UiJsonRenderSubmitRequest,
  UiJsonRenderSubmitResponse,
  UiRole,
  UiApiSource,
  UiApiSourceRequest,
  UiApiTag,
  UiApiTestLog,
  UiApiTestRequest,
  UiApiTestResponse,
  UiBuilderOverview,
  UiBuilderPageDetail,
  UiNodeBinding,
  UiNodeBindingRequest,
  UiOpenApiImportPayload,
  UiPage,
  UiPageNode,
  UiPageNodeRequest,
  UiPagePreviewResponse,
  UiPageRequest,
  UiProject,
  UiProjectRequest,
  UiSpecVersion,
} from './types'

async function unwrap<T>(promise: Promise<{ data: ApiResponse<T> }>) {
  const response = await promise
  return response.data.data
}

function buildPageParams(query?: PageQuery) {
  return {
    page: query?.page ?? 1,
    size: query?.size ?? 20,
  }
}

async function unwrapRemote<T>(promise: Promise<{ data: RemoteResponse<T> }>) {
  const response = await promise
  return response.data.data
}

export const uiBuilderApi = {
  getOverview() {
    return unwrap<UiBuilderOverview>(businessClient.get('/api/v1/ui-builder/overview'))
  },
  listSemanticFields(query?: PageQuery) {
    return unwrap<PageResult<SemanticFieldDict>>(businessClient.get('/api/v1/ui-builder/semantic-fields', {
      params: buildPageParams(query),
    }))
  },
  createSemanticField(payload: SemanticFieldDictRequest) {
    return unwrap<SemanticFieldDict>(businessClient.post('/api/v1/ui-builder/semantic-fields', payload))
  },
  updateSemanticField(dictId: number, payload: SemanticFieldDictRequest) {
    return unwrap<SemanticFieldDict>(businessClient.put(`/api/v1/ui-builder/semantic-fields/${dictId}`, payload))
  },
  deleteSemanticField(dictId: number) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/semantic-fields/${dictId}`))
  },
  listSemanticFieldAliases(standardKey: string, query?: PageQuery) {
    return unwrap<PageResult<SemanticFieldAlias>>(businessClient.get(`/api/v1/ui-builder/semantic-fields/${standardKey}/aliases`, {
      params: buildPageParams(query),
    }))
  },
  createSemanticFieldAlias(payload: SemanticFieldAliasRequest) {
    return unwrap<SemanticFieldAlias>(businessClient.post('/api/v1/ui-builder/semantic-field-aliases', payload))
  },
  updateSemanticFieldAlias(aliasId: number, payload: SemanticFieldAliasRequest) {
    return unwrap<SemanticFieldAlias>(businessClient.put(`/api/v1/ui-builder/semantic-field-aliases/${aliasId}`, payload))
  },
  deleteSemanticFieldAlias(aliasId: number) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/semantic-field-aliases/${aliasId}`))
  },
  listSemanticFieldValueMaps(standardKey: string, query?: PageQuery) {
    return unwrap<PageResult<SemanticFieldValueMap>>(businessClient.get(`/api/v1/ui-builder/semantic-fields/${standardKey}/value-maps`, {
      params: buildPageParams(query),
    }))
  },
  createSemanticFieldValueMap(payload: SemanticFieldValueMapRequest) {
    return unwrap<SemanticFieldValueMap>(businessClient.post('/api/v1/ui-builder/semantic-field-value-maps', payload))
  },
  updateSemanticFieldValueMap(valueMapId: number, payload: SemanticFieldValueMapRequest) {
    return unwrap<SemanticFieldValueMap>(businessClient.put(`/api/v1/ui-builder/semantic-field-value-maps/${valueMapId}`, payload))
  },
  deleteSemanticFieldValueMap(valueMapId: number) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/semantic-field-value-maps/${valueMapId}`))
  },
  async listRoles(appCode = 'AI-RND-WORKFLOW') {
    const result = await unwrapRemote<RemotePageResult<UiRole>>(businessClient.get('/api/v1/auth/roles', {
      params: {
        appCode,
        pageNo: 1,
        pageSize: 200,
      },
    }))
    return result.records
  },
  listSources(query?: PageQuery) {
    return unwrap<PageResult<UiApiSource>>(businessClient.get('/api/v1/ui-builder/sources', { params: buildPageParams(query) }))
  },
  listTags(sourceId: string, query?: PageQuery) {
    return unwrap<PageResult<UiApiTag>>(businessClient.get(`/api/v1/ui-builder/sources/${sourceId}/tags`, {
      params: buildPageParams(query),
    }))
  },
  createSource(payload: UiApiSourceRequest) {
    return unwrap<UiApiSource>(businessClient.post('/api/v1/ui-builder/sources', payload))
  },
  updateSource(sourceId: string, payload: UiApiSourceRequest) {
    return unwrap<UiApiSource>(businessClient.put(`/api/v1/ui-builder/sources/${sourceId}`, payload))
  },
  deleteSource(sourceId: string) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/sources/${sourceId}`))
  },
  listEndpoints(
    sourceId: string,
    query?: PageQuery,
    filters?: { tagId?: string; untagged?: boolean; name?: string; path?: string; status?: string },
  ) {
    return unwrap<PageResult<UiApiEndpoint>>(businessClient.get(`/api/v1/ui-builder/sources/${sourceId}/endpoints`, {
      params: {
        ...buildPageParams(query),
        ...(filters?.tagId ? { tagId: filters.tagId } : {}),
        ...(filters?.untagged ? { untagged: true } : {}),
        ...(filters?.name ? { name: filters.name } : {}),
        ...(filters?.path ? { path: filters.path } : {}),
        ...(filters?.status ? { status: filters.status } : {}),
      },
    }))
  },
  importOpenApi(sourceId: string, payload: UiOpenApiImportPayload, query?: PageQuery) {
    return unwrap<PageResult<UiApiEndpoint>>(
      businessClient.post(`/api/v1/ui-builder/sources/${sourceId}/import-openapi`, payload, {
        params: buildPageParams(query),
      }),
    )
  },
  createEndpoint(payload: UiApiEndpointRequest) {
    return unwrap<UiApiEndpoint>(businessClient.post('/api/v1/ui-builder/endpoints', payload))
  },
  updateEndpoint(endpointId: string, payload: UiApiEndpointRequest) {
    return unwrap<UiApiEndpoint>(businessClient.put(`/api/v1/ui-builder/endpoints/${endpointId}`, payload))
  },
  deleteEndpoint(endpointId: string) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/endpoints/${endpointId}`))
  },
  testEndpoint(endpointId: string, payload: UiApiTestRequest) {
    return unwrap<UiApiTestResponse>(businessClient.post(`/api/v1/ui-builder/endpoints/${endpointId}/test`, payload))
  },
  invokeEndpoint(endpointId: string, payload: UiApiInvokeRequest) {
    return unwrap<unknown>(businessClient.post(`/api/v1/ui-builder/runtime/endpoints/${endpointId}/invoke`, payload))
  },
  invokeEndpointAsJsonRender(endpointId: string, payload: UiJsonRenderInvokeRequest) {
    return unwrap<UiJsonRenderInvokeResponse>(businessClient.post(`/api/v1/ui-builder/runtime/endpoints/${endpointId}/render`, payload))
  },
  submitJsonRenderForm(payload: UiJsonRenderSubmitRequest) {
    return unwrap<UiJsonRenderSubmitResponse>(businessClient.post('/api/v1/ui-builder/runtime/forms/submit', payload))
  },
  listTestLogs(endpointId: string, query?: PageQuery) {
    return unwrap<PageResult<UiApiTestLog>>(businessClient.get(`/api/v1/ui-builder/endpoints/${endpointId}/test-logs`, {
      params: buildPageParams(query),
    }))
  },
  listFlowLogs(
    query?: PageQuery,
    filters?: { flowNum?: string; requestUrl?: string; createdBy?: string; invokeStatus?: string },
  ) {
    return unwrap<PageResult<UiApiFlowLog>>(businessClient.get('/api/v1/ui-builder/flow-logs', {
      params: {
        ...buildPageParams(query),
        ...(filters?.flowNum ? { flowNum: filters.flowNum } : {}),
        ...(filters?.requestUrl ? { requestUrl: filters.requestUrl } : {}),
        ...(filters?.createdBy ? { createdBy: filters.createdBy } : {}),
        ...(filters?.invokeStatus ? { invokeStatus: filters.invokeStatus } : {}),
      },
    }))
  },
  listEndpointRoleRelations(roleId?: string, query?: PageQuery) {
    return unwrap<PageResult<UiApiEndpointRole>>(businessClient.get('/api/v1/ui-builder/endpoint-role-relations', {
      params: {
        ...buildPageParams(query),
        ...(roleId ? { roleId } : {}),
      },
    }))
  },
  bindEndpointRoleRelations(payload: UiApiEndpointRoleBindRequest) {
    return unwrap<UiApiEndpointRole[]>(businessClient.post('/api/v1/ui-builder/endpoint-role-relations', payload))
  },
  deleteEndpointRoleRelation(relationId: string) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/endpoint-role-relations/${relationId}`))
  },
  listCards(
    query?: PageQuery,
    filters?: { name?: string; status?: string },
  ) {
    return unwrap<PageResult<UiCard>>(businessClient.get('/api/v1/ui-builder/cards', {
      params: {
        ...buildPageParams(query),
        ...(filters?.name ? { name: filters.name } : {}),
        ...(filters?.status ? { status: filters.status } : {}),
      },
    }))
  },
  createCard(payload: UiCardRequest) {
    return unwrap<UiCard>(businessClient.post('/api/v1/ui-builder/cards', payload))
  },
  updateCard(cardId: string, payload: UiCardRequest) {
    return unwrap<UiCard>(businessClient.put(`/api/v1/ui-builder/cards/${cardId}`, payload))
  },
  deleteCard(cardId: string) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/cards/${cardId}`))
  },
  listCardEndpointRelations(cardId: string, query?: PageQuery) {
    return unwrap<PageResult<UiCardEndpointRelation>>(businessClient.get(`/api/v1/ui-builder/cards/${cardId}/endpoint-relations`, {
      params: buildPageParams(query),
    }))
  },
  bindCardEndpointRelations(cardId: string, payload: UiCardEndpointBindRequest) {
    return unwrap<UiCardEndpointRelation[]>(businessClient.post(`/api/v1/ui-builder/cards/${cardId}/endpoint-relations`, payload))
  },
  deleteCardEndpointRelation(cardId: string, relationId: string) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/cards/${cardId}/endpoint-relations/${relationId}`))
  },
  listProjects(query?: PageQuery) {
    return unwrap<PageResult<UiProject>>(businessClient.get('/api/v1/ui-builder/projects', { params: buildPageParams(query) }))
  },
  createProject(payload: UiProjectRequest) {
    return unwrap<UiProject>(businessClient.post('/api/v1/ui-builder/projects', payload))
  },
  updateProject(projectId: string, payload: UiProjectRequest) {
    return unwrap<UiProject>(businessClient.put(`/api/v1/ui-builder/projects/${projectId}`, payload))
  },
  deleteProject(projectId: string) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/projects/${projectId}`))
  },
  listPages(projectId: string, query?: PageQuery) {
    return unwrap<PageResult<UiPage>>(businessClient.get(`/api/v1/ui-builder/projects/${projectId}/pages`, {
      params: buildPageParams(query),
    }))
  },
  createPage(projectId: string, payload: UiPageRequest) {
    return unwrap<UiPage>(businessClient.post(`/api/v1/ui-builder/projects/${projectId}/pages`, payload))
  },
  updatePage(pageId: string, payload: UiPageRequest) {
    return unwrap<UiPage>(businessClient.put(`/api/v1/ui-builder/pages/${pageId}`, payload))
  },
  deletePage(pageId: string) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/pages/${pageId}`))
  },
  getPageDetail(pageId: string) {
    return unwrap<UiBuilderPageDetail>(businessClient.get(`/api/v1/ui-builder/pages/${pageId}`))
  },
  listNodes(pageId: string, query?: PageQuery) {
    return unwrap<PageResult<UiPageNode>>(businessClient.get(`/api/v1/ui-builder/pages/${pageId}/nodes`, {
      params: buildPageParams(query),
    }))
  },
  createNode(pageId: string, payload: UiPageNodeRequest) {
    return unwrap<UiPageNode>(businessClient.post(`/api/v1/ui-builder/pages/${pageId}/nodes`, payload))
  },
  updateNode(nodeId: string, payload: UiPageNodeRequest) {
    return unwrap<UiPageNode>(businessClient.put(`/api/v1/ui-builder/nodes/${nodeId}`, payload))
  },
  deleteNode(nodeId: string) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/nodes/${nodeId}`))
  },
  listBindings(nodeId: string, query?: PageQuery) {
    return unwrap<PageResult<UiNodeBinding>>(businessClient.get(`/api/v1/ui-builder/nodes/${nodeId}/bindings`, {
      params: buildPageParams(query),
    }))
  },
  createBinding(nodeId: string, payload: UiNodeBindingRequest) {
    return unwrap<UiNodeBinding>(businessClient.post(`/api/v1/ui-builder/nodes/${nodeId}/bindings`, payload))
  },
  updateBinding(bindingId: string, payload: UiNodeBindingRequest) {
    return unwrap<UiNodeBinding>(businessClient.put(`/api/v1/ui-builder/bindings/${bindingId}`, payload))
  },
  deleteBinding(bindingId: string) {
    return unwrap<void>(businessClient.delete(`/api/v1/ui-builder/bindings/${bindingId}`))
  },
  previewPage(pageId: string) {
    return unwrap<UiPagePreviewResponse>(businessClient.get(`/api/v1/ui-builder/pages/${pageId}/preview`))
  },
  listVersions(pageId: string, query?: PageQuery) {
    return unwrap<PageResult<UiSpecVersion>>(businessClient.get(`/api/v1/ui-builder/pages/${pageId}/versions`, {
      params: buildPageParams(query),
    }))
  },
  publishPage(pageId: string) {
    return unwrap<UiSpecVersion>(businessClient.post(`/api/v1/ui-builder/pages/${pageId}/publish`))
  },
}
