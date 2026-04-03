import { useEffect, useState } from 'react'
import { Alert, Spin, Tabs, Typography, message } from 'antd'

import { uiBuilderApi } from './api'
import { OverviewTab } from './components/OverviewTab'
import { ReleaseTab } from './components/ReleaseTab'
import { SourceCenterTab } from './components/SourceCenterTab'
import { StudioTab } from './components/StudioTab'
import type {
  PageQuery,
  PageResult,
  UiApiEndpoint,
  UiApiEndpointRequest,
  UiApiSource,
  UiApiSourceRequest,
  UiApiTag,
  UiApiTestLog,
  UiApiTestRequest,
  UiApiTestResponse,
  UiBuilderOverview,
  UiBuilderPageDetail,
  UiOpenApiImportPayload,
  UiNodeBindingRequest,
  UiPage,
  UiPageNodeRequest,
  UiPagePreviewResponse,
  UiPageRequest,
  UiProject,
  UiProjectRequest,
  UiSpecVersion,
} from './types'

const DEFAULT_PAGE_SIZE = 20

interface PaginationState {
  page: number
  size: number
  total: number
}

function createPaginationState(): PaginationState {
  return {
    page: 1,
    size: DEFAULT_PAGE_SIZE,
    total: 0,
  }
}

function toPaginationState<T>(result: PageResult<T>): PaginationState {
  return {
    page: result.page,
    size: result.size,
    total: result.total,
  }
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error) {
    return error.message
  }
  return fallback
}

function buildEndpointFilters(tagFilter: string) {
  if (tagFilter === '__untagged__') {
    return { untagged: true }
  }
  if (tagFilter !== 'all') {
    return { tagId: tagFilter }
  }
  return undefined
}

export function UiBuilderPage() {
  const [messageApi, contextHolder] = message.useMessage()
  const [overview, setOverview] = useState<UiBuilderOverview | null>(null)
  const [sources, setSources] = useState<UiApiSource[]>([])
  const [endpoints, setEndpoints] = useState<UiApiEndpoint[]>([])
  const [tags, setTags] = useState<UiApiTag[]>([])
  const [testLogs, setTestLogs] = useState<UiApiTestLog[]>([])
  const [testResult, setTestResult] = useState<UiApiTestResponse | null>(null)
  const [projects, setProjects] = useState<UiProject[]>([])
  const [pages, setPages] = useState<UiPage[]>([])
  const [pageDetail, setPageDetail] = useState<UiBuilderPageDetail | null>(null)
  const [preview, setPreview] = useState<UiPagePreviewResponse | null>(null)
  const [versions, setVersions] = useState<UiSpecVersion[]>([])

  const [selectedSourceId, setSelectedSourceId] = useState<string>()
  const [selectedEndpointId, setSelectedEndpointId] = useState<string>()
  const [selectedProjectId, setSelectedProjectId] = useState<string>()
  const [selectedPageId, setSelectedPageId] = useState<string>()
  const [selectedEndpointTagFilter, setSelectedEndpointTagFilter] = useState<string>('all')

  const [sourcePagination, setSourcePagination] = useState<PaginationState>(createPaginationState())
  const [endpointPagination, setEndpointPagination] = useState<PaginationState>(createPaginationState())
  const [testLogPagination, setTestLogPagination] = useState<PaginationState>(createPaginationState())
  const [projectPagination, setProjectPagination] = useState<PaginationState>(createPaginationState())
  const [pagePagination, setPagePagination] = useState<PaginationState>(createPaginationState())
  const [versionPagination, setVersionPagination] = useState<PaginationState>(createPaginationState())

  const [booting, setBooting] = useState(true)
  const [sourceLoading, setSourceLoading] = useState(false)
  const [studioLoading, setStudioLoading] = useState(false)
  const [releaseLoading, setReleaseLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedEndpoint = endpoints.find((item) => item.id === selectedEndpointId)
  const selectedPage = pages.find((item) => item.id === selectedPageId)

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      setBooting(true)
      setError(null)
      try {
        const overviewData = await uiBuilderApi.getOverview()
        if (cancelled) {
          return
        }
        setOverview(overviewData)
      } catch (err) {
        if (!cancelled) {
          setError(getErrorMessage(err, '加载 UI Builder 页面失败'))
        }
      } finally {
        if (!cancelled) {
          setBooting(false)
        }
      }
    }

    void bootstrap()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadSources() {
      setSourceLoading(true)
      try {
        const result = await uiBuilderApi.listSources({
          page: sourcePagination.page,
          size: sourcePagination.size,
        })
        if (cancelled) {
          return
        }
        setSources(result.data)
        setSourcePagination(toPaginationState(result))
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载接口源失败'))
        }
      } finally {
        if (!cancelled) {
          setSourceLoading(false)
        }
      }
    }

    void loadSources()

    return () => {
      cancelled = true
    }
  }, [messageApi, sourcePagination.page, sourcePagination.size])

  useEffect(() => {
    let cancelled = false

    async function loadProjects() {
      setStudioLoading(true)
      try {
        const result = await uiBuilderApi.listProjects({
          page: projectPagination.page,
          size: projectPagination.size,
        })
        if (cancelled) {
          return
        }
        setProjects(result.data)
        setProjectPagination(toPaginationState(result))
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载项目列表失败'))
        }
      } finally {
        if (!cancelled) {
          setStudioLoading(false)
        }
      }
    }

    void loadProjects()

    return () => {
      cancelled = true
    }
  }, [messageApi, projectPagination.page, projectPagination.size])

  useEffect(() => {
    if (!sources.length) {
      setSelectedSourceId(undefined)
      return
    }

    if (!selectedSourceId || !sources.some((item) => item.id === selectedSourceId)) {
      setSelectedSourceId(sources[0].id)
    }
  }, [selectedSourceId, sources])

  useEffect(() => {
    if (!projects.length) {
      setSelectedProjectId(undefined)
      return
    }

    if (!selectedProjectId || !projects.some((item) => item.id === selectedProjectId)) {
      setSelectedProjectId(projects[0].id)
    }
  }, [projects, selectedProjectId])

  useEffect(() => {
    let cancelled = false

    async function loadEndpoints() {
      if (!selectedSourceId) {
        setEndpoints([])
        setTags([])
        setSelectedEndpointId(undefined)
        setTestLogs([])
        return
      }

      setSourceLoading(true)
      try {
        const [endpointResult, tagResult] = await Promise.all([
          uiBuilderApi.listEndpoints(
            selectedSourceId,
            {
              page: endpointPagination.page,
              size: endpointPagination.size,
            },
            buildEndpointFilters(selectedEndpointTagFilter),
          ),
          uiBuilderApi.listTags(selectedSourceId, { page: 1, size: 100 }),
        ])
        if (cancelled) {
          return
        }
        setEndpoints(endpointResult.data)
        setEndpointPagination(toPaginationState(endpointResult))
        setTags(tagResult.data)
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载接口定义失败'))
        }
      } finally {
        if (!cancelled) {
          setSourceLoading(false)
        }
      }
    }

    void loadEndpoints()

    return () => {
      cancelled = true
    }
  }, [
    endpointPagination.page,
    endpointPagination.size,
    messageApi,
    selectedEndpointTagFilter,
    selectedSourceId,
  ])

  useEffect(() => {
    if (!endpoints.length) {
      setSelectedEndpointId(undefined)
      setTestLogs([])
      return
    }

    if (!selectedEndpointId || !endpoints.some((item) => item.id === selectedEndpointId)) {
      setSelectedEndpointId(endpoints[0].id)
    }
  }, [endpoints, selectedEndpointId])

  useEffect(() => {
    let cancelled = false

    async function loadTestLogs() {
      if (!selectedEndpointId) {
        setTestLogs([])
        return
      }

      try {
        const result = await uiBuilderApi.listTestLogs(selectedEndpointId, {
          page: testLogPagination.page,
          size: testLogPagination.size,
        })
        if (!cancelled) {
          setTestLogs(result.data)
          setTestLogPagination(toPaginationState(result))
        }
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载联调日志失败'))
        }
      }
    }

    void loadTestLogs()

    return () => {
      cancelled = true
    }
  }, [messageApi, selectedEndpointId, testLogPagination.page, testLogPagination.size])

  useEffect(() => {
    let cancelled = false

    async function loadPages() {
      if (!selectedProjectId) {
        setPages([])
        setSelectedPageId(undefined)
        return
      }

      setStudioLoading(true)
      try {
        const result = await uiBuilderApi.listPages(selectedProjectId, {
          page: pagePagination.page,
          size: pagePagination.size,
        })
        if (!cancelled) {
          setPages(result.data)
          setPagePagination(toPaginationState(result))
        }
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载页面列表失败'))
        }
      } finally {
        if (!cancelled) {
          setStudioLoading(false)
        }
      }
    }

    void loadPages()

    return () => {
      cancelled = true
    }
  }, [messageApi, pagePagination.page, pagePagination.size, selectedProjectId])

  useEffect(() => {
    if (!pages.length) {
      setSelectedPageId(undefined)
      setPageDetail(null)
      setPreview(null)
      setVersions([])
      return
    }

    if (!selectedPageId || !pages.some((item) => item.id === selectedPageId)) {
      setSelectedPageId(pages[0].id)
    }
  }, [pages, selectedPageId])

  useEffect(() => {
    let cancelled = false

    async function loadPageWorkspace() {
      if (!selectedPageId) {
        setPageDetail(null)
        setPreview(null)
        return
      }

      setReleaseLoading(true)
      try {
        const detail = await uiBuilderApi.getPageDetail(selectedPageId)

        let previewData: UiPagePreviewResponse | null = null
        try {
          previewData = await uiBuilderApi.previewPage(selectedPageId)
        } catch {
          previewData = null
        }

        if (cancelled) {
          return
        }

        setPageDetail(detail)
        setPreview(previewData)
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载页面工作台失败'))
        }
      } finally {
        if (!cancelled) {
          setReleaseLoading(false)
        }
      }
    }

    void loadPageWorkspace()

    return () => {
      cancelled = true
    }
  }, [messageApi, selectedPageId])

  useEffect(() => {
    let cancelled = false

    async function loadVersions() {
      if (!selectedPageId) {
        setVersions([])
        return
      }

      setReleaseLoading(true)
      try {
        const result = await uiBuilderApi.listVersions(selectedPageId, {
          page: versionPagination.page,
          size: versionPagination.size,
        })
        if (!cancelled) {
          setVersions(result.data)
          setVersionPagination(toPaginationState(result))
        }
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载版本记录失败'))
        }
      } finally {
        if (!cancelled) {
          setReleaseLoading(false)
        }
      }
    }

    void loadVersions()

    return () => {
      cancelled = true
    }
  }, [messageApi, selectedPageId, versionPagination.page, versionPagination.size])

  async function reloadSources(preferredId?: string, query: PageQuery = sourcePagination) {
    const result = await uiBuilderApi.listSources(query)
    setSources(result.data)
    setSourcePagination(toPaginationState(result))
    if (preferredId && result.data.some((item) => item.id === preferredId)) {
      setSelectedSourceId(preferredId)
    }
  }

  async function reloadEndpoints(
    preferredId?: string,
    query: PageQuery = endpointPagination,
    tagFilter = selectedEndpointTagFilter,
  ) {
    if (!selectedSourceId) {
      setEndpoints([])
      setTags([])
      return
    }
    const [endpointResult, tagResult] = await Promise.all([
      uiBuilderApi.listEndpoints(selectedSourceId, query, buildEndpointFilters(tagFilter)),
      uiBuilderApi.listTags(selectedSourceId, { page: 1, size: 100 }),
    ])
    setEndpoints(endpointResult.data)
    setEndpointPagination(toPaginationState(endpointResult))
    setTags(tagResult.data)
    if (preferredId && endpointResult.data.some((item) => item.id === preferredId)) {
      setSelectedEndpointId(preferredId)
      return
    }
    if (endpointResult.data.length) {
      setSelectedEndpointId(endpointResult.data[0].id)
    }
  }

  async function reloadProjects(preferredId?: string, query: PageQuery = projectPagination) {
    const result = await uiBuilderApi.listProjects(query)
    setProjects(result.data)
    setProjectPagination(toPaginationState(result))
    if (preferredId && result.data.some((item) => item.id === preferredId)) {
      setSelectedProjectId(preferredId)
    }
  }

  async function reloadPages(projectId: string, preferredId?: string, query: PageQuery = pagePagination) {
    const result = await uiBuilderApi.listPages(projectId, query)
    setPages(result.data)
    setPagePagination(toPaginationState(result))
    if (preferredId && result.data.some((item) => item.id === preferredId)) {
      setSelectedPageId(preferredId)
      return
    }
    if (result.data.length) {
      setSelectedPageId(result.data[0].id)
    }
  }

  async function reloadPageWorkspace(pageId: string) {
    const detail = await uiBuilderApi.getPageDetail(pageId)

    let previewData: UiPagePreviewResponse | null = null
    try {
      previewData = await uiBuilderApi.previewPage(pageId)
    } catch {
      previewData = null
    }

    setPageDetail(detail)
    setPreview(previewData)
  }

  async function reloadVersions(pageId: string, query: PageQuery = versionPagination) {
    const result = await uiBuilderApi.listVersions(pageId, query)
    setVersions(result.data)
    setVersionPagination(toPaginationState(result))
  }

  function handleSelectSource(sourceId: string) {
    setSelectedSourceId(sourceId)
    setSelectedEndpointTagFilter('all')
    setEndpointPagination((prev) => ({ ...prev, page: 1, total: 0 }))
    setTestLogPagination((prev) => ({ ...prev, page: 1, total: 0 }))
    setTestResult(null)
  }

  function handleSelectEndpoint(endpointId: string) {
    setSelectedEndpointId(endpointId)
    setTestLogPagination((prev) => ({ ...prev, page: 1 }))
    setTestResult(null)
  }

  function handleSelectProject(projectId: string) {
    setSelectedProjectId(projectId)
    setPagePagination((prev) => ({ ...prev, page: 1, total: 0 }))
  }

  function handleSelectPage(pageId: string) {
    setSelectedPageId(pageId)
    setVersionPagination((prev) => ({ ...prev, page: 1, total: 0 }))
  }

  async function handleSaveSource(sourceId: string | undefined, payload: UiApiSourceRequest) {
    try {
      const saved = sourceId
        ? await uiBuilderApi.updateSource(sourceId, payload)
        : await uiBuilderApi.createSource(payload)
      await reloadSources(saved.id)
      messageApi.success(sourceId ? '接口源已更新' : '接口源已创建')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存接口源失败'))
      throw err
    }
  }

  async function handleDeleteSource(sourceId: string) {
    try {
      await uiBuilderApi.deleteSource(sourceId)
      await reloadSources(undefined, { page: 1, size: sourcePagination.size })
      setSourcePagination((prev) => ({ ...prev, page: 1 }))
      setEndpoints([])
      setTags([])
      setTestLogs([])
      setTestResult(null)
      messageApi.success('接口源已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除接口源失败'))
    }
  }

  async function handleImportOpenApi(sourceId: string, payload: UiOpenApiImportPayload) {
    try {
      await uiBuilderApi.importOpenApi(sourceId, payload, { page: 1, size: endpointPagination.size })
      if (sourceId === selectedSourceId) {
        await reloadEndpoints(undefined, { page: 1, size: endpointPagination.size })
        setEndpointPagination((prev) => ({ ...prev, page: 1 }))
      }
      messageApi.success('OpenAPI 文档已导入')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '导入 OpenAPI 失败'))
      throw err
    }
  }

  async function handleSaveEndpoint(endpointId: string | undefined, payload: UiApiEndpointRequest) {
    try {
      const saved = endpointId
        ? await uiBuilderApi.updateEndpoint(endpointId, payload)
        : await uiBuilderApi.createEndpoint(payload)
      await reloadEndpoints(saved.id)
      messageApi.success(endpointId ? '接口定义已更新' : '接口定义已创建')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存接口定义失败'))
      throw err
    }
  }

  async function handleDeleteEndpoint(endpointId: string) {
    try {
      await uiBuilderApi.deleteEndpoint(endpointId)
      await reloadEndpoints(undefined, { page: 1, size: endpointPagination.size })
      setEndpointPagination((prev) => ({ ...prev, page: 1 }))
      setTestResult(null)
      messageApi.success('接口定义已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除接口定义失败'))
    }
  }

  async function handleTestEndpoint(endpointId: string, payload: UiApiTestRequest) {
    try {
      const result = await uiBuilderApi.testEndpoint(endpointId, payload)
      const firstLogPage = await uiBuilderApi.listTestLogs(endpointId, { page: 1, size: testLogPagination.size })
      setTestResult(result)
      setSelectedEndpointId(endpointId)
      setTestLogs(firstLogPage.data)
      setTestLogPagination(toPaginationState(firstLogPage))
      messageApi.success(result.success ? '接口联调成功' : '接口联调失败')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '接口联调失败'))
      throw err
    }
  }

  async function handleSaveProject(projectId: string | undefined, payload: UiProjectRequest) {
    try {
      const saved = projectId
        ? await uiBuilderApi.updateProject(projectId, payload)
        : await uiBuilderApi.createProject(payload)
      await reloadProjects(saved.id)
      messageApi.success(projectId ? '项目已更新' : '项目已创建')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存项目失败'))
      throw err
    }
  }

  async function handleDeleteProject(projectId: string) {
    try {
      await uiBuilderApi.deleteProject(projectId)
      await reloadProjects(undefined, { page: 1, size: projectPagination.size })
      setProjectPagination((prev) => ({ ...prev, page: 1 }))
      setPages([])
      setPageDetail(null)
      setPreview(null)
      setVersions([])
      messageApi.success('项目已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除项目失败'))
    }
  }

  async function handleSavePage(projectId: string, pageId: string | undefined, payload: UiPageRequest) {
    try {
      const saved = pageId
        ? await uiBuilderApi.updatePage(pageId, payload)
        : await uiBuilderApi.createPage(projectId, payload)
      await reloadPages(projectId, saved.id)
      messageApi.success(pageId ? '页面已更新' : '页面已创建')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存页面失败'))
      throw err
    }
  }

  async function handleDeletePage(pageId: string) {
    if (!selectedProjectId) {
      return
    }
    try {
      await uiBuilderApi.deletePage(pageId)
      await reloadPages(selectedProjectId, undefined, { page: 1, size: pagePagination.size })
      setPagePagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success('页面已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除页面失败'))
    }
  }

  async function handleSaveNode(pageId: string, nodeId: string | undefined, payload: UiPageNodeRequest) {
    try {
      if (nodeId) {
        await uiBuilderApi.updateNode(nodeId, payload)
      } else {
        await uiBuilderApi.createNode(pageId, payload)
      }
      await reloadPageWorkspace(pageId)
      messageApi.success(nodeId ? '节点已更新' : '节点已创建')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存节点失败'))
      throw err
    }
  }

  async function handleDeleteNode(nodeId: string) {
    if (!selectedPageId) {
      return
    }
    try {
      await uiBuilderApi.deleteNode(nodeId)
      await reloadPageWorkspace(selectedPageId)
      messageApi.success('节点已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除节点失败'))
    }
  }

  async function handleSaveBinding(nodeId: string, bindingId: string | undefined, payload: UiNodeBindingRequest) {
    if (!selectedPageId) {
      return
    }
    try {
      if (bindingId) {
        await uiBuilderApi.updateBinding(bindingId, payload)
      } else {
        await uiBuilderApi.createBinding(nodeId, payload)
      }
      await reloadPageWorkspace(selectedPageId)
      messageApi.success(bindingId ? '字段绑定已更新' : '字段绑定已创建')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存字段绑定失败'))
      throw err
    }
  }

  async function handleDeleteBinding(bindingId: string) {
    if (!selectedPageId) {
      return
    }
    try {
      await uiBuilderApi.deleteBinding(bindingId)
      await reloadPageWorkspace(selectedPageId)
      messageApi.success('字段绑定已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除字段绑定失败'))
    }
  }

  async function handleRefreshPreview(pageId: string) {
    try {
      let previewData: UiPagePreviewResponse | null = null
      try {
        previewData = await uiBuilderApi.previewPage(pageId)
      } catch {
        previewData = null
      }
      setPreview(previewData)
      if (pageId === selectedPageId) {
        const detail = await uiBuilderApi.getPageDetail(pageId)
        setPageDetail(detail)
      }
      messageApi.success(previewData ? '预览已刷新' : '当前页面还没有节点，预览已清空')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '刷新预览失败'))
      throw err
    }
  }

  async function handlePublishPage(pageId: string) {
    try {
      await uiBuilderApi.publishPage(pageId)
      await Promise.all([
        reloadPageWorkspace(pageId),
        reloadVersions(pageId, { page: 1, size: versionPagination.size }),
      ])
      setVersionPagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success('页面已发布新版本')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '发布失败'))
      throw err
    }
  }

  if (booting) {
    return (
      <div className="flex justify-center py-16">
        {contextHolder}
        <Spin size="large" tip="正在加载 UI Builder 工作台" />
      </div>
    )
  }

  if (error || !overview) {
    return (
      <>
        {contextHolder}
        <Alert
          type="error"
          showIcon
          message="UI Builder 加载失败"
          description={error ?? '未获取到概览数据'}
        />
      </>
    )
  }

  return (
    <div className="space-y-6">
      {contextHolder}
      <section className="rounded-[28px] border border-slate-200/80 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.14),_transparent_38%),linear-gradient(135deg,#ffffff_0%,#f8fbff_52%,#eef6ff_100%)] px-8 py-8 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <Typography.Text type="secondary">UI Builder / OpenAPI to json-render</Typography.Text>
            <Typography.Title level={2} style={{ margin: 0 }}>
              接口文档、页面编排、字段绑定和版本发布一站式工作台
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0, maxWidth: 980 }}>
              现在这页已经不是静态流程介绍了。你可以在这里创建接口源、导入 OpenAPI、手工补接口定义、配置项目页面、维护节点和字段绑定，并直接生成当前 json-render spec。
            </Typography.Paragraph>
          </div>
          <div className="grid grid-cols-2 gap-3 rounded-[24px] border border-sky-100 bg-white/90 p-4 shadow-sm">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-400">接口源</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{sourcePagination.total}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-400">页面</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{pagePagination.total}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-400">节点</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{pageDetail?.nodes.length ?? 0}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-400">版本</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{versionPagination.total}</div>
            </div>
          </div>
        </div>
      </section>

      <Tabs
        size="large"
        items={[
          {
            key: 'overview',
            label: '流程与模型',
            children: <OverviewTab overview={overview} />,
          },
          {
            key: 'sources',
            label: '接口中心',
            children: (
              <SourceCenterTab
                sources={sources}
                endpoints={endpoints}
                tags={tags}
                authTypes={overview.authTypes}
                selectedSourceId={selectedSourceId}
                selectedEndpointId={selectedEndpointId}
                selectedEndpoint={selectedEndpoint}
                selectedTagFilter={selectedEndpointTagFilter}
                testResult={testResult}
                testLogs={testLogs}
                loading={sourceLoading}
                sourcePagination={{
                  current: sourcePagination.page,
                  pageSize: sourcePagination.size,
                  total: sourcePagination.total,
                }}
                endpointPagination={{
                  current: endpointPagination.page,
                  pageSize: endpointPagination.size,
                  total: endpointPagination.total,
                }}
                logPagination={{
                  current: testLogPagination.page,
                  pageSize: testLogPagination.size,
                  total: testLogPagination.total,
                }}
                onSelectSource={handleSelectSource}
                onSelectEndpoint={handleSelectEndpoint}
                onTagFilterChange={(value) => {
                  setSelectedEndpointTagFilter(value)
                  setEndpointPagination((prev) => ({ ...prev, page: 1 }))
                }}
                onSourcePageChange={(page, size) => {
                  setSourcePagination((prev) => ({ ...prev, page, size }))
                }}
                onEndpointPageChange={(page, size) => {
                  setEndpointPagination((prev) => ({ ...prev, page, size }))
                }}
                onLogPageChange={(page, size) => {
                  setTestLogPagination((prev) => ({ ...prev, page, size }))
                }}
                onSaveSource={handleSaveSource}
                onDeleteSource={handleDeleteSource}
                onImportOpenApi={handleImportOpenApi}
                onSaveEndpoint={handleSaveEndpoint}
                onDeleteEndpoint={handleDeleteEndpoint}
                onTestEndpoint={handleTestEndpoint}
                onRefreshEndpoints={async () => {
                  await reloadEndpoints(selectedEndpointId)
                }}
              />
            ),
          },
          {
            key: 'studio',
            label: '页面工作台',
            children: (
              <StudioTab
                projects={projects}
                pages={pages}
                pageDetail={pageDetail}
                selectedProjectId={selectedProjectId}
                selectedPageId={selectedPageId}
                preview={preview}
                nodeTypes={overview.nodeTypes}
                endpoints={endpoints}
                loading={studioLoading || releaseLoading}
                projectPagination={{
                  current: projectPagination.page,
                  pageSize: projectPagination.size,
                  total: projectPagination.total,
                }}
                pagePagination={{
                  current: pagePagination.page,
                  pageSize: pagePagination.size,
                  total: pagePagination.total,
                }}
                onProjectPageChange={(page, size) => {
                  setProjectPagination((prev) => ({ ...prev, page, size }))
                }}
                onPagePageChange={(page, size) => {
                  setPagePagination((prev) => ({ ...prev, page, size }))
                }}
                onSelectProject={handleSelectProject}
                onSelectPage={handleSelectPage}
                onSaveProject={handleSaveProject}
                onDeleteProject={handleDeleteProject}
                onSavePage={handleSavePage}
                onDeletePage={handleDeletePage}
                onSaveNode={handleSaveNode}
                onDeleteNode={handleDeleteNode}
                onSaveBinding={handleSaveBinding}
                onDeleteBinding={handleDeleteBinding}
                onRefreshPreview={handleRefreshPreview}
              />
            ),
          },
          {
            key: 'release',
            label: '预览与发布',
            children: (
              <ReleaseTab
                selectedPage={selectedPage}
                preview={preview}
                versions={versions}
                loading={releaseLoading}
                versionPagination={{
                  current: versionPagination.page,
                  pageSize: versionPagination.size,
                  total: versionPagination.total,
                }}
                onVersionPageChange={(page, size) => {
                  setVersionPagination((prev) => ({ ...prev, page, size }))
                }}
                onRefreshPreview={handleRefreshPreview}
                onPublishPage={handlePublishPage}
              />
            ),
          },
        ]}
      />
    </div>
  )
}
