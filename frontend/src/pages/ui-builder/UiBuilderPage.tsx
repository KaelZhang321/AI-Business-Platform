import { useEffect, useState } from 'react'
import { Alert, Spin, Tabs, Typography, message } from 'antd'

import { uiBuilderApi } from './api'
import { CardWorkbenchTab } from './components/CardWorkbenchTab'
import { EndpointRoleTab } from './components/EndpointRoleTab'
import { FlowLogTab } from './components/FlowLogTab'
import { JsonRenderPlaygroundTab } from './components/JsonRenderPlaygroundTab'
import { LowCodeBuilderTab } from './components/LowCodeBuilderTab'
import { OverviewTab } from './components/OverviewTab'
import { SemanticFieldTab } from './components/SemanticFieldTab'
import { SourceCenterTab } from './components/SourceCenterTab'
import { RuleEngineTab } from './rule/RuleEngineTab'
import type {
  PageQuery,
  PageResult,
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
  UiApiSource,
  UiApiSourceRequest,
  UiApiTag,
  UiApiTestLog,
  UiApiTestRequest,
  UiApiTestResponse,
  UiBuilderOverview,
  UiCard,
  UiCardEndpointRelation,
  UiCardRequest,
  UiOpenApiImportPayload,
  UiRole,
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

function buildEndpointQueryFilters(
  tagFilter: string,
  endpointKeyword: string,
  endpointPathKeyword: string,
  endpointStatusFilter: string,
) {
  return {
    ...buildEndpointFilters(tagFilter),
    ...(endpointKeyword.trim() ? { name: endpointKeyword.trim() } : {}),
    ...(endpointPathKeyword.trim() ? { path: endpointPathKeyword.trim() } : {}),
    ...(endpointStatusFilter !== 'all' ? { status: endpointStatusFilter } : {}),
  }
}

export function UiBuilderPage() {
  const [messageApi, contextHolder] = message.useMessage()
  const [overview, setOverview] = useState<UiBuilderOverview | null>(null)
  const [semanticFields, setSemanticFields] = useState<SemanticFieldDict[]>([])
  const [semanticFieldAliases, setSemanticFieldAliases] = useState<SemanticFieldAlias[]>([])
  const [semanticFieldValueMaps, setSemanticFieldValueMaps] = useState<SemanticFieldValueMap[]>([])
  const [sources, setSources] = useState<UiApiSource[]>([])
  const [endpoints, setEndpoints] = useState<UiApiEndpoint[]>([])
  const [tags, setTags] = useState<UiApiTag[]>([])
  const [roles, setRoles] = useState<UiRole[]>([])
  const [endpointRoleRelations, setEndpointRoleRelations] = useState<UiApiEndpointRole[]>([])
  const [testLogs, setTestLogs] = useState<UiApiTestLog[]>([])
  const [flowLogs, setFlowLogs] = useState<UiApiFlowLog[]>([])
  const [testResult, setTestResult] = useState<UiApiTestResponse | null>(null)
  const [cards, setCards] = useState<UiCard[]>([])
  const [cardEndpointRelations, setCardEndpointRelations] = useState<UiCardEndpointRelation[]>([])

  const [selectedSourceId, setSelectedSourceId] = useState<string>()
  const [selectedEndpointId, setSelectedEndpointId] = useState<string>()
  const [selectedSemanticFieldId, setSelectedSemanticFieldId] = useState<number>()
  const [selectedRoleId, setSelectedRoleId] = useState<string>()
  const [selectedCardId, setSelectedCardId] = useState<string>()
  const [selectedEndpointTagFilter, setSelectedEndpointTagFilter] = useState<string>('all')
  const [endpointKeyword, setEndpointKeyword] = useState('')
  const [endpointPathKeyword, setEndpointPathKeyword] = useState('')
  const [endpointStatusFilter, setEndpointStatusFilter] = useState('all')
  const [flowLogFlowNum, setFlowLogFlowNum] = useState('')
  const [flowLogRequestUrl, setFlowLogRequestUrl] = useState('')
  const [flowLogCreatedBy, setFlowLogCreatedBy] = useState('')
  const [flowLogInvokeStatus, setFlowLogInvokeStatus] = useState('')

  const [sourcePagination, setSourcePagination] = useState<PaginationState>(createPaginationState())
  const [semanticFieldPagination, setSemanticFieldPagination] = useState<PaginationState>(createPaginationState())
  const [semanticAliasPagination, setSemanticAliasPagination] = useState<PaginationState>(createPaginationState())
  const [semanticValueMapPagination, setSemanticValueMapPagination] = useState<PaginationState>(createPaginationState())
  const [endpointPagination, setEndpointPagination] = useState<PaginationState>(createPaginationState())
  const [roleRelationPagination, setRoleRelationPagination] = useState<PaginationState>(createPaginationState())
  const [testLogPagination, setTestLogPagination] = useState<PaginationState>(createPaginationState())
  const [flowLogPagination, setFlowLogPagination] = useState<PaginationState>(createPaginationState())
  const [cardPagination, setCardPagination] = useState<PaginationState>(createPaginationState())
  const [cardRelationPagination, setCardRelationPagination] = useState<PaginationState>(createPaginationState())

  const [booting, setBooting] = useState(true)
  const [sourceLoading, setSourceLoading] = useState(false)
  const [semanticLoading, setSemanticLoading] = useState(false)
  const [roleLoading, setRoleLoading] = useState(false)
  const [cardLoading, setCardLoading] = useState(false)
  const [flowLogLoading, setFlowLogLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedEndpoint = endpoints.find((item) => item.id === selectedEndpointId)
  const selectedSemanticField = semanticFields.find((item) => item.id === selectedSemanticFieldId)

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

    async function loadSemanticFields() {
      setSemanticLoading(true)
      try {
        const result = await uiBuilderApi.listSemanticFields({
          page: semanticFieldPagination.page,
          size: semanticFieldPagination.size,
        })
        if (!cancelled) {
          setSemanticFields(result.data)
          setSemanticFieldPagination(toPaginationState(result))
        }
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载语义字段字典失败'))
        }
      } finally {
        if (!cancelled) {
          setSemanticLoading(false)
        }
      }
    }

    void loadSemanticFields()

    return () => {
      cancelled = true
    }
  }, [messageApi, semanticFieldPagination.page, semanticFieldPagination.size])

  useEffect(() => {
    let cancelled = false

    async function loadRoles() {
      setRoleLoading(true)
      try {
        const result = await uiBuilderApi.listRoles()
        if (!cancelled) {
          setRoles(result)
        }
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载角色列表失败'))
        }
      } finally {
        if (!cancelled) {
          setRoleLoading(false)
        }
      }
    }

    void loadRoles()

    return () => {
      cancelled = true
    }
  }, [messageApi])

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

    async function loadCards() {
      setCardLoading(true)
      try {
        const result = await uiBuilderApi.listCards({
          page: cardPagination.page,
          size: cardPagination.size,
        })
        if (cancelled) {
          return
        }
        setCards(result.data)
        setCardPagination(toPaginationState(result))
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载卡片列表失败'))
        }
      } finally {
        if (!cancelled) {
          setCardLoading(false)
        }
      }
    }

    void loadCards()

    return () => {
      cancelled = true
    }
  }, [cardPagination.page, cardPagination.size, messageApi])

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
    if (!cards.length) {
      setSelectedCardId(undefined)
      setCardEndpointRelations([])
      return
    }
    if (!selectedCardId || !cards.some((item) => item.id === selectedCardId)) {
      setSelectedCardId(cards[0].id)
    }
  }, [cards, selectedCardId])

  useEffect(() => {
    if (!semanticFields.length) {
      setSelectedSemanticFieldId(undefined)
      setSemanticFieldAliases([])
      setSemanticFieldValueMaps([])
      return
    }

    if (!selectedSemanticFieldId || !semanticFields.some((item) => item.id === selectedSemanticFieldId)) {
      setSelectedSemanticFieldId(semanticFields[0].id)
    }
  }, [selectedSemanticFieldId, semanticFields])

  useEffect(() => {
    if (!roles.length) {
      setSelectedRoleId(undefined)
      return
    }

    if (!selectedRoleId || !roles.some((item) => item.id === selectedRoleId)) {
      setSelectedRoleId(roles[0].id)
    }
  }, [roles, selectedRoleId])

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
            buildEndpointQueryFilters(selectedEndpointTagFilter, endpointKeyword, endpointPathKeyword, endpointStatusFilter),
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
    endpointKeyword,
    endpointPathKeyword,
    endpointStatusFilter,
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

    async function loadCardRelations() {
      if (!selectedCardId) {
        setCardEndpointRelations([])
        return
      }
      setCardLoading(true)
      try {
        const result = await uiBuilderApi.listCardEndpointRelations(selectedCardId, {
          page: cardRelationPagination.page,
          size: cardRelationPagination.size,
        })
        if (!cancelled) {
          setCardEndpointRelations(result.data)
          setCardRelationPagination(toPaginationState(result))
        }
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载卡片接口关系失败'))
        }
      } finally {
        if (!cancelled) {
          setCardLoading(false)
        }
      }
    }

    void loadCardRelations()

    return () => {
      cancelled = true
    }
  }, [cardRelationPagination.page, cardRelationPagination.size, messageApi, selectedCardId])

  useEffect(() => {
    let cancelled = false

    async function loadFlowLogs() {
      setFlowLogLoading(true)
      try {
        const result = await uiBuilderApi.listFlowLogs(
          {
            page: flowLogPagination.page,
            size: flowLogPagination.size,
          },
          {
            ...(flowLogFlowNum.trim() ? { flowNum: flowLogFlowNum.trim() } : {}),
            ...(flowLogRequestUrl.trim() ? { requestUrl: flowLogRequestUrl.trim() } : {}),
            ...(flowLogCreatedBy.trim() ? { createdBy: flowLogCreatedBy.trim() } : {}),
            ...(flowLogInvokeStatus.trim() ? { invokeStatus: flowLogInvokeStatus.trim() } : {}),
          },
        )
        if (!cancelled) {
          setFlowLogs(result.data)
          setFlowLogPagination(toPaginationState(result))
        }
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载调用日志失败'))
        }
      } finally {
        if (!cancelled) {
          setFlowLogLoading(false)
        }
      }
    }

    void loadFlowLogs()

    return () => {
      cancelled = true
    }
  }, [
    flowLogCreatedBy,
    flowLogFlowNum,
    flowLogInvokeStatus,
    flowLogPagination.page,
    flowLogPagination.size,
    flowLogRequestUrl,
    messageApi,
  ])

  useEffect(() => {
    let cancelled = false

    async function loadSemanticFieldDetails() {
      if (!selectedSemanticField?.standardKey) {
        setSemanticFieldAliases([])
        setSemanticFieldValueMaps([])
        return
      }

      setSemanticLoading(true)
      try {
        const [aliasResult, valueMapResult] = await Promise.all([
          uiBuilderApi.listSemanticFieldAliases(selectedSemanticField.standardKey, {
            page: semanticAliasPagination.page,
            size: semanticAliasPagination.size,
          }),
          uiBuilderApi.listSemanticFieldValueMaps(selectedSemanticField.standardKey, {
            page: semanticValueMapPagination.page,
            size: semanticValueMapPagination.size,
          }),
        ])
        if (!cancelled) {
          setSemanticFieldAliases(aliasResult.data)
          setSemanticAliasPagination(toPaginationState(aliasResult))
          setSemanticFieldValueMaps(valueMapResult.data)
          setSemanticValueMapPagination(toPaginationState(valueMapResult))
        }
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载语义字段明细失败'))
        }
      } finally {
        if (!cancelled) {
          setSemanticLoading(false)
        }
      }
    }

    void loadSemanticFieldDetails()

    return () => {
      cancelled = true
    }
  }, [
    messageApi,
    selectedSemanticField?.standardKey,
    semanticAliasPagination.page,
    semanticAliasPagination.size,
    semanticValueMapPagination.page,
    semanticValueMapPagination.size,
  ])

  useEffect(() => {
    let cancelled = false

    async function loadEndpointRoleRelations() {
      if (!selectedRoleId) {
        setEndpointRoleRelations([])
        return
      }

      setRoleLoading(true)
      try {
        const result = await uiBuilderApi.listEndpointRoleRelations(selectedRoleId, {
          page: roleRelationPagination.page,
          size: roleRelationPagination.size,
        })
        if (!cancelled) {
          setEndpointRoleRelations(result.data)
          setRoleRelationPagination(toPaginationState(result))
        }
      } catch (err) {
        if (!cancelled) {
          messageApi.error(getErrorMessage(err, '加载接口角色关系失败'))
        }
      } finally {
        if (!cancelled) {
          setRoleLoading(false)
        }
      }
    }

    void loadEndpointRoleRelations()

    return () => {
      cancelled = true
    }
  }, [messageApi, roleRelationPagination.page, roleRelationPagination.size, selectedRoleId])

  async function reloadSources(preferredId?: string, query: PageQuery = sourcePagination) {
    const result = await uiBuilderApi.listSources(query)
    setSources(result.data)
    setSourcePagination(toPaginationState(result))
    if (preferredId && result.data.some((item) => item.id === preferredId)) {
      setSelectedSourceId(preferredId)
    }
  }

  async function reloadCards(preferredId?: string, query: PageQuery = cardPagination) {
    const result = await uiBuilderApi.listCards(query)
    setCards(result.data)
    setCardPagination(toPaginationState(result))
    if (preferredId && result.data.some((item) => item.id === preferredId)) {
      setSelectedCardId(preferredId)
      return
    }
    if (result.data.length) {
      setSelectedCardId(result.data[0].id)
    }
  }

  async function reloadCardRelations(cardId = selectedCardId, query: PageQuery = cardRelationPagination) {
    if (!cardId) {
      setCardEndpointRelations([])
      return
    }
    const result = await uiBuilderApi.listCardEndpointRelations(cardId, query)
    setCardEndpointRelations(result.data)
    setCardRelationPagination(toPaginationState(result))
  }

  async function reloadSemanticFields(preferredId?: number, query: PageQuery = semanticFieldPagination) {
    const result = await uiBuilderApi.listSemanticFields(query)
    setSemanticFields(result.data)
    setSemanticFieldPagination(toPaginationState(result))
    if (preferredId && result.data.some((item) => item.id === preferredId)) {
      setSelectedSemanticFieldId(preferredId)
      return
    }
    if (result.data.length) {
      setSelectedSemanticFieldId(result.data[0].id)
    }
  }

  async function reloadSemanticFieldDetails(
    standardKey = selectedSemanticField?.standardKey,
    aliasQuery: PageQuery = semanticAliasPagination,
    valueMapQuery: PageQuery = semanticValueMapPagination,
  ) {
    if (!standardKey) {
      setSemanticFieldAliases([])
      setSemanticFieldValueMaps([])
      return
    }
    const [aliasResult, valueMapResult] = await Promise.all([
      uiBuilderApi.listSemanticFieldAliases(standardKey, aliasQuery),
      uiBuilderApi.listSemanticFieldValueMaps(standardKey, valueMapQuery),
    ])
    setSemanticFieldAliases(aliasResult.data)
    setSemanticAliasPagination(toPaginationState(aliasResult))
    setSemanticFieldValueMaps(valueMapResult.data)
    setSemanticValueMapPagination(toPaginationState(valueMapResult))
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
      uiBuilderApi.listEndpoints(
        selectedSourceId,
        query,
        buildEndpointQueryFilters(tagFilter, endpointKeyword, endpointPathKeyword, endpointStatusFilter),
      ),
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

  async function reloadRoles(preferredId?: string) {
    const result = await uiBuilderApi.listRoles()
    setRoles(result)
    if (preferredId && result.some((item) => item.id === preferredId)) {
      setSelectedRoleId(preferredId)
      return
    }
    if (result.length) {
      setSelectedRoleId(result[0].id)
    }
  }

  async function reloadEndpointRoleRelations(roleId = selectedRoleId, query: PageQuery = roleRelationPagination) {
    if (!roleId) {
      setEndpointRoleRelations([])
      return
    }
    const result = await uiBuilderApi.listEndpointRoleRelations(roleId, query)
    setEndpointRoleRelations(result.data)
    setRoleRelationPagination(toPaginationState(result))
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

  async function handleSaveSemanticField(dictId: number | undefined, payload: SemanticFieldDictRequest) {
    try {
      const saved = dictId
        ? await uiBuilderApi.updateSemanticField(dictId, payload)
        : await uiBuilderApi.createSemanticField(payload)
      await reloadSemanticFields(saved.id)
      messageApi.success(dictId ? '语义字段已更新' : '语义字段已创建')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存语义字段失败'))
      throw err
    }
  }

  async function handleDeleteSemanticField(dictId: number) {
    try {
      await uiBuilderApi.deleteSemanticField(dictId)
      await reloadSemanticFields(undefined, { page: 1, size: semanticFieldPagination.size })
      setSemanticFieldPagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success('语义字段已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除语义字段失败'))
    }
  }

  async function handleSaveSemanticFieldAlias(aliasId: number | undefined, payload: SemanticFieldAliasRequest) {
    try {
      await (aliasId
        ? uiBuilderApi.updateSemanticFieldAlias(aliasId, payload)
        : uiBuilderApi.createSemanticFieldAlias(payload))
      await reloadSemanticFieldDetails(payload.standardKey, { page: 1, size: semanticAliasPagination.size }, semanticValueMapPagination)
      setSemanticAliasPagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success(aliasId ? '字段别名已更新' : '字段别名已创建')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存字段别名失败'))
      throw err
    }
  }

  async function handleDeleteSemanticFieldAlias(aliasId: number) {
    if (!selectedSemanticField?.standardKey) {
      return
    }
    try {
      await uiBuilderApi.deleteSemanticFieldAlias(aliasId)
      await reloadSemanticFieldDetails(selectedSemanticField.standardKey, { page: 1, size: semanticAliasPagination.size }, semanticValueMapPagination)
      setSemanticAliasPagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success('字段别名已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除字段别名失败'))
    }
  }

  async function handleSaveSemanticFieldValueMap(
    valueMapId: number | undefined,
    payload: SemanticFieldValueMapRequest,
  ) {
    try {
      await (valueMapId
        ? uiBuilderApi.updateSemanticFieldValueMap(valueMapId, payload)
        : uiBuilderApi.createSemanticFieldValueMap(payload))
      await reloadSemanticFieldDetails(payload.standardKey, semanticAliasPagination, { page: 1, size: semanticValueMapPagination.size })
      setSemanticValueMapPagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success(valueMapId ? '字段值映射已更新' : '字段值映射已创建')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存字段值映射失败'))
      throw err
    }
  }

  async function handleDeleteSemanticFieldValueMap(valueMapId: number) {
    if (!selectedSemanticField?.standardKey) {
      return
    }
    try {
      await uiBuilderApi.deleteSemanticFieldValueMap(valueMapId)
      await reloadSemanticFieldDetails(selectedSemanticField.standardKey, semanticAliasPagination, { page: 1, size: semanticValueMapPagination.size })
      setSemanticValueMapPagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success('字段值映射已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除字段值映射失败'))
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

  async function handleBindEndpointRoleRelations(payload: UiApiEndpointRoleBindRequest) {
    try {
      await uiBuilderApi.bindEndpointRoleRelations(payload)
      await reloadEndpointRoleRelations(payload.roleId, { page: 1, size: roleRelationPagination.size })
      setRoleRelationPagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success('接口角色关系已保存')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存接口角色关系失败'))
      throw err
    }
  }

  async function handleDeleteEndpointRoleRelation(relationId: string) {
    try {
      await uiBuilderApi.deleteEndpointRoleRelation(relationId)
      await reloadEndpointRoleRelations(selectedRoleId, { page: 1, size: roleRelationPagination.size })
      setRoleRelationPagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success('接口角色关系已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除接口角色关系失败'))
    }
  }

  async function handleLoadEndpointsBySource(sourceId: string) {
    const result = await uiBuilderApi.listEndpoints(sourceId, { page: 1, size: 100 })
    return result.data
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

  async function handleSaveCard(cardId: string | undefined, payload: UiCardRequest) {
    try {
      const saved = cardId
        ? await uiBuilderApi.updateCard(cardId, payload)
        : await uiBuilderApi.createCard(payload)
      await reloadCards(saved.id)
      messageApi.success(cardId ? '卡片已更新' : '卡片已创建')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存卡片失败'))
      throw err
    }
  }

  async function handleDeleteCard(cardId: string) {
    try {
      await uiBuilderApi.deleteCard(cardId)
      await reloadCards(undefined, { page: 1, size: cardPagination.size })
      setCardPagination((prev) => ({ ...prev, page: 1 }))
      setCardRelationPagination((prev) => ({ ...prev, page: 1, total: 0 }))
      setCardEndpointRelations([])
      messageApi.success('卡片已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除卡片失败'))
    }
  }

  async function handleBindCardRelations(cardId: string, endpointIds: string[]) {
    try {
      await uiBuilderApi.bindCardEndpointRelations(cardId, { endpointIds })
      await reloadCardRelations(cardId, { page: 1, size: cardRelationPagination.size })
      setCardRelationPagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success('卡片接口关联已保存')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '保存卡片接口关联失败'))
      throw err
    }
  }

  async function handleDeleteCardRelation(cardId: string, relationId: string) {
    try {
      await uiBuilderApi.deleteCardEndpointRelation(cardId, relationId)
      await reloadCardRelations(cardId, { page: 1, size: cardRelationPagination.size })
      setCardRelationPagination((prev) => ({ ...prev, page: 1 }))
      messageApi.success('卡片接口关联已删除')
    } catch (err) {
      messageApi.error(getErrorMessage(err, '删除卡片接口关联失败'))
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
              接口文档、卡片编排、角色映射和运行时调用一站式工作台
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0, maxWidth: 980 }}>
              当前工作流已经切换为卡片驱动。你可以在这里管理接口源、导入 OpenAPI、定义接口、维护语义字典、配置接口角色，并把接口绑定到工作台卡片。
            </Typography.Paragraph>
          </div>
          <div className="grid grid-cols-2 gap-3 rounded-[24px] border border-sky-100 bg-white/90 p-4 shadow-sm">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-400">接口源</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{sourcePagination.total}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-400">接口</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{endpointPagination.total}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-400">卡片</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{cardPagination.total}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-slate-400">调用日志</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">{flowLogPagination.total}</div>
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
                endpointKeyword={endpointKeyword}
                endpointPathKeyword={endpointPathKeyword}
                endpointStatusFilter={endpointStatusFilter}
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
                onEndpointKeywordChange={(value) => {
                  setEndpointKeyword(value)
                  setEndpointPagination((prev) => ({ ...prev, page: 1 }))
                }}
                onEndpointPathKeywordChange={(value) => {
                  setEndpointPathKeyword(value)
                  setEndpointPagination((prev) => ({ ...prev, page: 1 }))
                }}
                onEndpointStatusFilterChange={(value) => {
                  setEndpointStatusFilter(value)
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
            key: 'semantic',
            label: '语义字典',
            children: (
              <SemanticFieldTab
                semanticFields={semanticFields}
                aliases={semanticFieldAliases}
                valueMaps={semanticFieldValueMaps}
                selectedSemanticFieldId={selectedSemanticFieldId}
                loading={semanticLoading}
                fieldPagination={{
                  current: semanticFieldPagination.page,
                  pageSize: semanticFieldPagination.size,
                  total: semanticFieldPagination.total,
                }}
                aliasPagination={{
                  current: semanticAliasPagination.page,
                  pageSize: semanticAliasPagination.size,
                  total: semanticAliasPagination.total,
                }}
                valueMapPagination={{
                  current: semanticValueMapPagination.page,
                  pageSize: semanticValueMapPagination.size,
                  total: semanticValueMapPagination.total,
                }}
                onSelectSemanticField={(dictId) => {
                  setSelectedSemanticFieldId(dictId)
                  setSemanticAliasPagination((prev) => ({ ...prev, page: 1, total: 0 }))
                  setSemanticValueMapPagination((prev) => ({ ...prev, page: 1, total: 0 }))
                }}
                onFieldPageChange={(page, size) => {
                  setSemanticFieldPagination((prev) => ({ ...prev, page, size }))
                }}
                onAliasPageChange={(page, size) => {
                  setSemanticAliasPagination((prev) => ({ ...prev, page, size }))
                }}
                onValueMapPageChange={(page, size) => {
                  setSemanticValueMapPagination((prev) => ({ ...prev, page, size }))
                }}
                onSaveSemanticField={handleSaveSemanticField}
                onDeleteSemanticField={handleDeleteSemanticField}
                onSaveAlias={handleSaveSemanticFieldAlias}
                onDeleteAlias={handleDeleteSemanticFieldAlias}
                onSaveValueMap={handleSaveSemanticFieldValueMap}
                onDeleteValueMap={handleDeleteSemanticFieldValueMap}
              />
            ),
          },
          {
            key: 'endpoint-roles',
            label: '接口角色',
            children: (
              <EndpointRoleTab
                roles={roles}
                sources={sources}
                relations={endpointRoleRelations}
                selectedRoleId={selectedRoleId}
                loading={roleLoading}
                relationPagination={{
                  current: roleRelationPagination.page,
                  pageSize: roleRelationPagination.size,
                  total: roleRelationPagination.total,
                }}
                onSelectRole={(roleId) => {
                  setSelectedRoleId(roleId)
                  setRoleRelationPagination((prev) => ({ ...prev, page: 1, total: 0 }))
                }}
                onRelationPageChange={(page, size) => {
                  setRoleRelationPagination((prev) => ({ ...prev, page, size }))
                }}
                onRefreshRoles={async () => {
                  await reloadRoles(selectedRoleId)
                }}
                onLoadEndpointsBySource={handleLoadEndpointsBySource}
                onBindRelations={handleBindEndpointRoleRelations}
                onDeleteRelation={handleDeleteEndpointRoleRelation}
              />
            ),
          },
          {
            key: 'flow-logs',
            label: '调用日志',
            children: (
              <FlowLogTab
                logs={flowLogs}
                loading={flowLogLoading}
                filters={{
                  flowNum: flowLogFlowNum,
                  requestUrl: flowLogRequestUrl,
                  createdBy: flowLogCreatedBy,
                  invokeStatus: flowLogInvokeStatus,
                }}
                pagination={{
                  current: flowLogPagination.page,
                  pageSize: flowLogPagination.size,
                  total: flowLogPagination.total,
                }}
                onFlowNumChange={(value) => {
                  setFlowLogFlowNum(value)
                  setFlowLogPagination((prev) => ({ ...prev, page: 1 }))
                }}
                onRequestUrlChange={(value) => {
                  setFlowLogRequestUrl(value)
                  setFlowLogPagination((prev) => ({ ...prev, page: 1 }))
                }}
                onCreatedByChange={(value) => {
                  setFlowLogCreatedBy(value)
                  setFlowLogPagination((prev) => ({ ...prev, page: 1 }))
                }}
                onInvokeStatusChange={(value) => {
                  setFlowLogInvokeStatus(value)
                  setFlowLogPagination((prev) => ({ ...prev, page: 1 }))
                }}
                onPageChange={(page, size) => {
                  setFlowLogPagination((prev) => ({ ...prev, page, size }))
                }}
              />
            ),
          },
          {
            key: 'studio',
            label: '页面工作台',
            children: (
              <CardWorkbenchTab
                cards={cards}
                relations={cardEndpointRelations}
                sources={sources}
                selectedCardId={selectedCardId}
                loading={cardLoading}
                cardPagination={{
                  current: cardPagination.page,
                  pageSize: cardPagination.size,
                  total: cardPagination.total,
                }}
                relationPagination={{
                  current: cardRelationPagination.page,
                  pageSize: cardRelationPagination.size,
                  total: cardRelationPagination.total,
                }}
                onSelectCard={(cardId) => {
                  setSelectedCardId(cardId)
                  setCardRelationPagination((prev) => ({ ...prev, page: 1, total: 0 }))
                }}
                onCardPageChange={(page, size) => {
                  setCardPagination((prev) => ({ ...prev, page, size }))
                }}
                onRelationPageChange={(page, size) => {
                  setCardRelationPagination((prev) => ({ ...prev, page, size }))
                }}
                onSaveCard={handleSaveCard}
                onDeleteCard={handleDeleteCard}
                onBindRelations={handleBindCardRelations}
                onDeleteRelation={handleDeleteCardRelation}
                onLoadEndpointsBySource={handleLoadEndpointsBySource}
              />
            ),
          },
          {
            key: 'rule-engine',
            label: '规则引擎',
            children: <RuleEngineTab />,
          },
          {
            key: 'lowcode-builder',
            label: '低代码搭建器',
            children: <LowCodeBuilderTab />,
          },
          {
            key: 'json-render-playground',
            label: 'JSON 预览器',
            children: <JsonRenderPlaygroundTab />,
          },
        ]}
      />
    </div>
  )
}
