import { businessClient } from '../../services/api'
import type {
  ApiResponse,
  PageQuery,
  PageResult,
  UiApiEndpoint,
  UiApiEndpointRequest,
  UiApiInvokeRequest,
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

export const uiBuilderApi = {
  getOverview() {
    return unwrap<UiBuilderOverview>(businessClient.get('/api/v1/ui-builder/overview'))
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
  listEndpoints(sourceId: string, query?: PageQuery, filters?: { tagId?: string; untagged?: boolean }) {
    return unwrap<PageResult<UiApiEndpoint>>(businessClient.get(`/api/v1/ui-builder/sources/${sourceId}/endpoints`, {
      params: {
        ...buildPageParams(query),
        ...(filters?.tagId ? { tagId: filters.tagId } : {}),
        ...(filters?.untagged ? { untagged: true } : {}),
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
  listTestLogs(endpointId: string, query?: PageQuery) {
    return unwrap<PageResult<UiApiTestLog>>(businessClient.get(`/api/v1/ui-builder/endpoints/${endpointId}/test-logs`, {
      params: buildPageParams(query),
    }))
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
