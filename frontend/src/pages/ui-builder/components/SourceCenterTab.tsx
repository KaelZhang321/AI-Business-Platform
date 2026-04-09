import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Descriptions,
  Divider,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'

import {
  buildFieldOrchestration,
  formatDateTime,
  inferDefaultPaginationConfig,
  mergePaginationConfigIntoFieldOrchestration,
  parseFieldOrchestrationConfig,
  parseJsonInput,
  prettyJson,
} from '../helpers'
import type {
  UiApiEndpoint,
  UiApiEndpointRequest,
  UiApiSource,
  UiApiSourceRequest,
  UiApiTag,
  UiApiTestLog,
  UiApiTestRequest,
  UiApiTestResponse,
  UiBuilderAuthType,
} from '../types'

const sourceTypeOptions = [
  { label: 'OpenAPI', value: 'openapi' },
  { label: 'Manual', value: 'manual' },
  { label: 'Postman', value: 'postman' },
]

const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' },
]

const methodOptions = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'].map((value) => ({
  label: value,
  value,
}))

const operationSafetyOptions = [
  { label: 'Query', value: 'query' },
  { label: 'List', value: 'list' },
  { label: 'Mutation', value: 'mutation' },
]

const paginationRequestTargetOptions = [
  { label: 'Query 参数', value: 'query' },
  { label: 'Body 请求体', value: 'body' },
]

interface SourceCenterTabProps {
  sources: UiApiSource[]
  endpoints: UiApiEndpoint[]
  tags: UiApiTag[]
  authTypes: UiBuilderAuthType[]
  selectedSourceId?: string
  selectedEndpointId?: string
  selectedEndpoint?: UiApiEndpoint
  selectedTagFilter: string
  testResult?: UiApiTestResponse | null
  testLogs: UiApiTestLog[]
  loading: boolean
  sourcePagination: {
    current: number
    pageSize: number
    total: number
  }
  endpointPagination: {
    current: number
    pageSize: number
    total: number
  }
  logPagination: {
    current: number
    pageSize: number
    total: number
  }
  onSelectSource: (sourceId: string) => void
  onSelectEndpoint: (endpointId: string) => void
  onTagFilterChange: (value: string) => void
  onSourcePageChange: (page: number, size: number) => void
  onEndpointPageChange: (page: number, size: number) => void
  onLogPageChange: (page: number, size: number) => void
  onSaveSource: (sourceId: string | undefined, payload: UiApiSourceRequest) => Promise<void>
  onDeleteSource: (sourceId: string) => Promise<void>
  onImportOpenApi: (sourceId: string, payload: { document?: string; documentUrl?: string }) => Promise<void>
  onSaveEndpoint: (endpointId: string | undefined, payload: UiApiEndpointRequest) => Promise<void>
  onDeleteEndpoint: (endpointId: string) => Promise<void>
  onTestEndpoint: (endpointId: string, payload: UiApiTestRequest) => Promise<void>
  onRefreshEndpoints: () => Promise<void>
}

interface EndpointFormValues extends UiApiEndpointRequest {
  paginationRequestTarget?: 'query' | 'body'
  paginationCurrentKey?: string
  paginationSizeKey?: string
}

export function SourceCenterTab({
  sources,
  endpoints,
  tags,
  authTypes,
  selectedSourceId,
  selectedEndpointId,
  selectedEndpoint,
  selectedTagFilter,
  testResult,
  testLogs,
  loading,
  sourcePagination,
  endpointPagination,
  logPagination,
  onSelectSource,
  onSelectEndpoint,
  onTagFilterChange,
  onSourcePageChange,
  onEndpointPageChange,
  onLogPageChange,
  onSaveSource,
  onDeleteSource,
  onImportOpenApi,
  onSaveEndpoint,
  onDeleteEndpoint,
  onTestEndpoint,
  onRefreshEndpoints,
}: SourceCenterTabProps) {
  const [sourceModalOpen, setSourceModalOpen] = useState(false)
  const [endpointModalOpen, setEndpointModalOpen] = useState(false)
  const [openApiModalOpen, setOpenApiModalOpen] = useState(false)
  const [testModalOpen, setTestModalOpen] = useState(false)
  const [editingSource, setEditingSource] = useState<UiApiSource | null>(null)
  const [editingEndpoint, setEditingEndpoint] = useState<UiApiEndpoint | null>(null)

  const [sourceForm] = Form.useForm<UiApiSourceRequest>()
  const [endpointForm] = Form.useForm<EndpointFormValues>()
  const [openApiForm] = Form.useForm<{ document?: string; documentUrl?: string }>()
  const [testForm] = Form.useForm<{ headers?: string; queryParams?: string; body?: string; createdBy?: string }>()
  const [messageApi, contextHolder] = message.useMessage()

  const selectedSource = useMemo(
    () => sources.find((item) => item.id === selectedSourceId),
    [selectedSourceId, sources],
  )
  const currentTestEndpoint = selectedEndpoint
  const tagOptions = useMemo(
    () => tags.map((tag) => ({ label: tag.name, value: tag.id })),
    [tags],
  )
  const filterOptions = useMemo(
    () => [
      { label: '全部标签', value: 'all' },
      { label: '未分组', value: '__untagged__' },
      ...tags.map((tag) => ({ label: tag.name, value: tag.id })),
    ],
    [tags],
  )

  useEffect(() => {
    if (selectedTagFilter === 'all' || selectedTagFilter === '__untagged__') {
      return
    }
    if (!tags.some((tag) => tag.id === selectedTagFilter)) {
      onTagFilterChange('all')
    }
  }, [onTagFilterChange, selectedTagFilter, tags])

  const sourceColumns = useMemo<TableColumnsType<UiApiSource>>(() => ([
    {
      title: '接口源',
      key: 'source',
      render: (_, record) => (
        <button
          className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
            record.id === selectedSourceId
              ? 'border-sky-300 bg-sky-50'
              : 'border-slate-200 bg-white hover:border-slate-300'
          }`}
          onClick={() => onSelectSource(record.id)}
          type="button"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="font-medium text-slate-900">{record.name}</div>
              <div className="text-xs text-slate-500">{record.code}</div>
            </div>
            <Tag color={record.status === 'active' ? 'green' : 'default'}>{record.status ?? 'draft'}</Tag>
          </div>
          <div className="mt-2 text-xs text-slate-500">{record.baseUrl || '未配置基础地址'}</div>
        </button>
      ),
    },
  ]), [onSelectSource, selectedSourceId])

  const endpointColumns = useMemo<TableColumnsType<UiApiEndpoint>>(() => ([
    {
      title: '方法',
      dataIndex: 'method',
      key: 'method',
      width: 96,
      render: (value: string) => (
        <Tag color={value === 'GET' ? 'blue' : value === 'POST' ? 'green' : 'purple'}>{value}</Tag>
      ),
    },
    {
      title: '接口',
      key: 'name',
      render: (_, record) => (
        <button
          className="w-full text-left"
          type="button"
          onClick={() => onSelectEndpoint(record.id)}
        >
          <div className="font-medium text-slate-900">{record.name}</div>
          <div className="text-xs text-slate-500">{record.path}</div>
        </button>
      ),
    },
    {
      title: '标签',
      dataIndex: 'tagName',
      key: 'tagName',
      width: 140,
      render: (value?: string | null) => value ? <Tag color="cyan">{value}</Tag> : <Tag>未分组</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (value: string) => <Tag color={value === 'active' ? 'green' : 'default'}>{value}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 260,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" onClick={() => openEndpointModal(record)}>
            编辑
          </Button>
          <Button size="small" onClick={() => openEndpointModal(record, true)}>
            补全编排
          </Button>
          <Button size="small" onClick={() => openTestModal(record)}>
            联调
          </Button>
          <Popconfirm title="删除接口定义？" onConfirm={() => onDeleteEndpoint(record.id)}>
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [onDeleteEndpoint, onSelectEndpoint])

  const logColumns = useMemo<TableColumnsType<UiApiTestLog>>(() => ([
    {
      title: '时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 180,
      render: (value?: string | null) => formatDateTime(value),
    },
    {
      title: '状态',
      key: 'status',
      width: 100,
      render: (_, record) => (
        <Tag color={record.successFlag === 1 ? 'green' : 'red'}>
          {record.successFlag === 1 ? '成功' : '失败'}
        </Tag>
      ),
    },
    {
      title: 'HTTP',
      dataIndex: 'responseStatus',
      key: 'responseStatus',
      width: 100,
      render: (value?: number | null) => value ?? '-',
    },
    {
      title: '请求地址',
      dataIndex: 'requestUrl',
      key: 'requestUrl',
      ellipsis: true,
    },
  ]), [])

  function openSourceModal(source?: UiApiSource) {
    setEditingSource(source ?? null)
    setSourceModalOpen(true)
    sourceForm.setFieldsValue({
      name: source?.name ?? '',
      code: source?.code ?? '',
      description: source?.description ?? '',
      sourceType: source?.sourceType ?? 'openapi',
      baseUrl: source?.baseUrl ?? '',
      docUrl: source?.docUrl ?? '',
      authType: source?.authType ?? 'none',
      authConfig: prettyJson(source?.authConfig ?? '{}'),
      defaultHeaders: prettyJson(source?.defaultHeaders ?? '{}'),
      env: source?.env ?? 'dev',
      status: source?.status ?? 'draft',
      createdBy: source?.createdBy ?? 'ui-builder',
    })
  }

  function openEndpointModal(endpoint?: UiApiEndpoint, autofillFieldOrchestration = false) {
    if (!selectedSourceId && !endpoint?.sourceId) {
      return
    }
    const defaultPaginationConfig = inferDefaultPaginationConfig(endpoint?.method ?? 'GET', endpoint?.operationSafety ?? 'query')
    const initialFieldOrchestration = endpoint?.fieldOrchestration ?? {
      fieldConfig: {
        ignore: [],
        passthrough: [],
        groups: [],
        render: [],
        ...(defaultPaginationConfig ? { pagination: defaultPaginationConfig } : {}),
      },
    }
    const orchestrationConfig = parseFieldOrchestrationConfig(initialFieldOrchestration)
    const paginationConfig = orchestrationConfig.fieldConfig.pagination ?? defaultPaginationConfig

    setEditingEndpoint(endpoint ?? null)
    setEndpointModalOpen(true)
    endpointForm.setFieldsValue({
      sourceId: endpoint?.sourceId ?? selectedSourceId ?? '',
      tagId: endpoint?.tagId ?? undefined,
      name: endpoint?.name ?? '',
      path: endpoint?.path ?? '',
      method: endpoint?.method ?? 'GET',
      operationSafety: endpoint?.operationSafety ?? 'query',
      summary: endpoint?.summary ?? '',
      requestContentType: endpoint?.requestContentType ?? 'application/json',
      requestSchema: prettyJson(endpoint?.requestSchema ?? '{}'),
      responseSchema: prettyJson(endpoint?.responseSchema ?? '{}'),
      sampleRequest: prettyJson(endpoint?.sampleRequest ?? '{}'),
      sampleResponse: prettyJson(endpoint?.sampleResponse ?? '{}'),
      fieldOrchestration: prettyJson(initialFieldOrchestration),
      paginationRequestTarget: paginationConfig?.requestTarget,
      paginationCurrentKey: paginationConfig?.currentKey,
      paginationSizeKey: paginationConfig?.sizeKey,
      status: endpoint?.status ?? 'active',
    })

    if (autofillFieldOrchestration) {
      const generated = buildFieldOrchestration(
        endpoint?.responseSchema,
        endpoint?.sampleResponse,
        initialFieldOrchestration,
      )
      endpointForm.setFieldValue('fieldOrchestration', prettyJson(generated))
    }
  }

  function openTestModal(endpoint?: UiApiEndpoint) {
    const target = endpoint ?? selectedEndpoint
    if (!target) {
      return
    }
    onSelectEndpoint(target.id)
    setTestModalOpen(true)
    testForm.setFieldsValue({
      headers: '{}',
      queryParams: '{}',
      body: prettyJson(target.sampleRequest ?? '{}'),
      createdBy: 'ui-builder',
    })
  }

  async function submitSource() {
    const values = await sourceForm.validateFields()
    await onSaveSource(editingSource?.id, values)
    setSourceModalOpen(false)
    setEditingSource(null)
    sourceForm.resetFields()
  }

  async function submitEndpoint() {
    const values = await endpointForm.validateFields()
    const mergedFieldOrchestration = mergePaginationConfigIntoFieldOrchestration(values.fieldOrchestration, {
      requestTarget: values.paginationRequestTarget,
      currentKey: values.paginationCurrentKey,
      sizeKey: values.paginationSizeKey,
    })
    await onSaveEndpoint(editingEndpoint?.id, {
      ...values,
      fieldOrchestration: prettyJson(mergedFieldOrchestration),
    })
    setEndpointModalOpen(false)
    setEditingEndpoint(null)
    endpointForm.resetFields()
  }

  function handleGenerateFieldOrchestration() {
    const values = endpointForm.getFieldsValue([
      'responseSchema',
      'sampleResponse',
      'fieldOrchestration',
      'method',
      'operationSafety',
      'paginationRequestTarget',
      'paginationCurrentKey',
      'paginationSizeKey',
    ])
    const defaultPaginationConfig = inferDefaultPaginationConfig(values.method, values.operationSafety)
    const generated = buildFieldOrchestration(
      values.responseSchema,
      values.sampleResponse,
      mergePaginationConfigIntoFieldOrchestration(values.fieldOrchestration, {
        requestTarget: values.paginationRequestTarget ?? defaultPaginationConfig?.requestTarget,
        currentKey: values.paginationCurrentKey ?? defaultPaginationConfig?.currentKey,
        sizeKey: values.paginationSizeKey ?? defaultPaginationConfig?.sizeKey,
      }),
    )
    endpointForm.setFieldValue('fieldOrchestration', prettyJson(generated))
    messageApi.success('已根据响应参数补全字段编排 JSON')
  }

  async function submitImportOpenApi() {
    const values = await openApiForm.validateFields()
    if (!selectedSourceId) {
      return
    }
    await onImportOpenApi(selectedSourceId, {
      document: values.document,
      documentUrl: values.documentUrl,
    })
    setOpenApiModalOpen(false)
    openApiForm.resetFields()
  }

  async function submitTest() {
    try {
      if (!selectedEndpointId) {
        return
      }
      const values = await testForm.validateFields()
      await onTestEndpoint(selectedEndpointId, {
        headers: parseJsonInput(values.headers),
        queryParams: parseJsonInput(values.queryParams),
        body: parseJsonInput(values.body),
        createdBy: values.createdBy,
      })
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '接口联调失败，请检查 JSON 输入')
      throw error
    }
  }

  return (
    <div className="space-y-6">
      {contextHolder}
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={7}>
          <Card
            title="接口源"
            extra={
              <Button type="primary" onClick={() => openSourceModal()}>
                新建接口源
              </Button>
            }
            className="rounded-[24px]"
          >
            <Table
              rowKey="id"
              loading={loading}
              dataSource={sources}
              columns={sourceColumns}
              pagination={{
                current: sourcePagination.current,
                pageSize: sourcePagination.pageSize,
                total: sourcePagination.total,
                showSizeChanger: true,
                onChange: onSourcePageChange,
              }}
              showHeader={false}
              locale={{ emptyText: <Empty description="还没有接口源" /> }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={17}>
          <div className="space-y-4">
            <Card
              title="接口源详情"
              className="rounded-[24px]"
              extra={selectedSource ? (
                <Space>
                  <Button onClick={() => openSourceModal(selectedSource)}>编辑</Button>
                  <Button onClick={() => setOpenApiModalOpen(true)}>导入 OpenAPI</Button>
                  <Popconfirm title="删除当前接口源？" onConfirm={() => onDeleteSource(selectedSource.id)}>
                    <Button danger>删除</Button>
                  </Popconfirm>
                </Space>
              ) : undefined}
            >
              {selectedSource ? (
                <Descriptions column={{ xs: 1, md: 2 }} size="small">
                  <Descriptions.Item label="编码">{selectedSource.code}</Descriptions.Item>
                  <Descriptions.Item label="来源类型">{selectedSource.sourceType}</Descriptions.Item>
                  <Descriptions.Item label="认证方式">{selectedSource.authType}</Descriptions.Item>
                  <Descriptions.Item label="环境">{selectedSource.env ?? '-'}</Descriptions.Item>
                  <Descriptions.Item label="基础地址" span={2}>
                    {selectedSource.baseUrl || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="文档地址" span={2}>
                    {selectedSource.docUrl || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="标签数" span={2}>
                    <Space wrap>
                      {tags.length
                        ? tags.map((tag) => (
                          <Tag key={tag.id} color="cyan">
                            {tag.name}
                          </Tag>
                        ))
                        : '暂无标签'}
                    </Space>
                  </Descriptions.Item>
                </Descriptions>
              ) : (
                <Empty description="请选择左侧接口源" />
              )}
            </Card>

            <Card
              title="接口定义"
              className="rounded-[24px]"
              extra={selectedSource ? (
                <Space>
                  <Select
                    value={selectedTagFilter}
                    options={filterOptions}
                    style={{ width: 180 }}
                    onChange={onTagFilterChange}
                    placeholder="按标签筛选"
                  />
                  <Button
                    onClick={() => {
                      void onRefreshEndpoints().catch(() => undefined)
                    }}
                  >
                    刷新
                  </Button>
                  <Button type="primary" onClick={() => openEndpointModal()}>
                    新建接口
                  </Button>
                </Space>
              ) : undefined}
            >
              <Table
                rowKey="id"
                loading={loading}
                dataSource={endpoints}
                columns={endpointColumns}
                pagination={{
                  current: endpointPagination.current,
                  pageSize: endpointPagination.pageSize,
                  total: endpointPagination.total,
                  showSizeChanger: true,
                  onChange: onEndpointPageChange,
                }}
                locale={{ emptyText: <Empty description="当前接口源下还没有接口定义" /> }}
              />
            </Card>
          </div>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="联调响应" className="rounded-[24px]">
            {selectedEndpoint ? (
              <div className="space-y-4">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <Typography.Text strong>{selectedEndpoint.name}</Typography.Text>
                  <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 8 }}>
                    {selectedEndpoint.method} {selectedEndpoint.path}
                  </Typography.Paragraph>
                </div>
                {testResult ? (
                  <>
                    <Alert
                      type={testResult.success ? 'success' : 'error'}
                      showIcon
                      message={testResult.success ? '联调成功' : '联调失败'}
                      description={testResult.errorMessage ?? `HTTP ${testResult.responseStatus ?? '-'}`}
                    />
                    <pre className="max-h-[420px] overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-100">
                      {prettyJson(testResult.responseBody)}
                    </pre>
                  </>
                ) : (
                  <Empty description="还没有联调结果，点击接口行上的“联调”发起一次测试" />
                )}
              </div>
            ) : (
              <Empty description="先在上面选一个接口定义" />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={12}>
          <Card title="联调日志" className="rounded-[24px]">
            <Table
              rowKey="id"
              loading={loading}
              dataSource={testLogs}
              columns={logColumns}
              pagination={{
                current: logPagination.current,
                pageSize: logPagination.pageSize,
                total: logPagination.total,
                showSizeChanger: true,
                onChange: onLogPageChange,
              }}
              locale={{ emptyText: <Empty description="当前接口还没有联调日志" /> }}
            />
          </Card>
        </Col>
      </Row>

      <Modal
        title={editingSource ? '编辑接口源' : '新建接口源'}
        open={sourceModalOpen}
        onOk={() => {
          void submitSource().catch(() => undefined)
        }}
        onCancel={() => setSourceModalOpen(false)}
        width={760}
        destroyOnHidden
      >
        <Form layout="vertical" form={sourceForm}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入接口源名称' }]}>
                <Input placeholder="例如：CRM OpenAPI" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="code" label="编码" rules={[{ required: true, message: '请输入唯一编码' }]}>
                <Input placeholder="crm_openapi" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="sourceType" label="来源类型" rules={[{ required: true }]}>
                <Select options={sourceTypeOptions} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="authType" label="认证方式" rules={[{ required: true }]}>
                <Select options={authTypes.map((item) => ({ label: `${item.type} | ${item.description}`, value: item.type }))} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="baseUrl" label="基础地址">
                <Input placeholder="https://api.example.com" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="docUrl" label="文档地址">
                <Input placeholder="https://api.example.com/openapi.json" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="env" label="环境">
                <Input placeholder="dev / test / prod" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="status" label="状态">
                <Select options={statusOptions} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="authConfig" label="认证配置(JSON)">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="defaultHeaders" label="默认请求头(JSON)">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="createdBy" label="创建人">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingEndpoint ? '编辑接口定义' : '新建接口定义'}
        open={endpointModalOpen}
        onOk={() => {
          void submitEndpoint().catch(() => undefined)
        }}
        onCancel={() => setEndpointModalOpen(false)}
        width={900}
        destroyOnHidden
      >
        <Form
          layout="vertical"
          form={endpointForm}
          onValuesChange={(changedValues, allValues) => {
            if (!('method' in changedValues) && !('operationSafety' in changedValues)) {
              return
            }
            if (allValues.paginationRequestTarget || allValues.paginationCurrentKey || allValues.paginationSizeKey) {
              return
            }
            const inferred = inferDefaultPaginationConfig(allValues.method, allValues.operationSafety)
            if (!inferred) {
              return
            }
            endpointForm.setFieldsValue({
              paginationRequestTarget: inferred.requestTarget,
              paginationCurrentKey: inferred.currentKey,
              paginationSizeKey: inferred.sizeKey,
            })
          }}
        >
          <Alert
            type="info"
            showIcon
            message="这里同时支持手工录入接口定义和 OpenAPI 导入后的精修。"
            className="mb-4"
          />
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="sourceId" label="接口源ID" rules={[{ required: true }]}>
                <Input disabled />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="tagId" label="接口标签">
                <Select allowClear options={tagOptions} placeholder="导入 OpenAPI 后可选择对应标签" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="接口名称" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="summary" label="接口摘要">
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="method" label="HTTP 方法" rules={[{ required: true }]}>
                <Select options={methodOptions} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="operationSafety" label="操作安全等级" initialValue="query">
                <Select options={operationSafetyOptions} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="path" label="接口路径" rules={[{ required: true }]}>
                <Input placeholder="/api/orders/list" />
              </Form.Item>
            </Col>
          </Row>
          <Divider orientation="left">分页映射</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="paginationRequestTarget" label="分页参数位置">
                <Select allowClear options={paginationRequestTargetOptions} placeholder="query / body" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="paginationCurrentKey" label="当前页字段">
                <Input placeholder="current / pageNo" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="paginationSizeKey" label="每页条数字段">
                <Input placeholder="size / pageSize" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="requestContentType" label="请求类型">
            <Input placeholder="application/json" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="requestSchema" label="请求 Schema(JSON)">
                <Input.TextArea rows={6} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="responseSchema" label="响应 Schema(JSON)">
                <Input.TextArea rows={6} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="sampleRequest" label="样例请求(JSON)">
                <Input.TextArea rows={6} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="sampleResponse" label="样例响应(JSON)">
                <Input.TextArea rows={6} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            name="fieldOrchestration"
            label={(
              <Space>
                <span>字段编排(JSON)</span>
                <Button size="small" type="link" onClick={handleGenerateFieldOrchestration}>
                  根据响应参数补全
                </Button>
              </Space>
            )}
            extra="系统会根据当前响应 Schema 和样例响应，自动生成 ignore/passthrough/groups/render 结构。"
          >
            <Input.TextArea rows={10} />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={statusOptions} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="导入 OpenAPI 文档"
        open={openApiModalOpen}
        onOk={() => {
          void submitImportOpenApi().catch(() => undefined)
        }}
        onCancel={() => setOpenApiModalOpen(false)}
        width={920}
        destroyOnHidden
      >
        <Form layout="vertical" form={openApiForm}>
          <Form.Item name="documentUrl" label="Swagger / OpenAPI 地址">
            <Input placeholder="https://example.com/v3/api-docs" />
          </Form.Item>
          <Form.Item
            name="document"
            label="OpenAPI / Swagger JSON"
            extra="支持两种导入方式：直接粘贴 JSON，或者填写上面的 Swagger 地址。两者都不填时，会回退到接口源上配置的 docUrl。"
          >
            <Input.TextArea rows={18} placeholder='{"openapi":"3.0.0","paths":{...}}' />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="接口联调"
        open={testModalOpen}
        onOk={() => {
          void submitTest().catch(() => undefined)
        }}
        onCancel={() => setTestModalOpen(false)}
        width={860}
        destroyOnHidden
      >
        {currentTestEndpoint ? (
          <>
            <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <Typography.Text strong>{currentTestEndpoint.name}</Typography.Text>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 8 }}>
                {currentTestEndpoint.method} {currentTestEndpoint.path}
              </Typography.Paragraph>
            </div>
            <Collapse
              className="mb-4 overflow-hidden rounded-2xl border border-slate-200 bg-white"
              items={[
                {
                  key: 'schema-preview',
                  label: '当前接口出入参与样例',
                  children: (
                    <Row gutter={[16, 16]}>
                      <Col span={12}>
                        <Card size="small" title="请求参数定义">
                          <pre className="max-h-[220px] overflow-auto rounded-2xl bg-slate-950 p-3 text-xs text-slate-100">
                            {prettyJson(currentTestEndpoint.requestSchema ?? '{}')}
                          </pre>
                        </Card>
                      </Col>
                      <Col span={12}>
                        <Card size="small" title="响应参数定义">
                          <pre className="max-h-[220px] overflow-auto rounded-2xl bg-slate-950 p-3 text-xs text-slate-100">
                            {prettyJson(currentTestEndpoint.responseSchema ?? '{}')}
                          </pre>
                        </Card>
                      </Col>
                      <Col span={12}>
                        <Card size="small" title="样例请求">
                          <pre className="max-h-[220px] overflow-auto rounded-2xl bg-slate-950 p-3 text-xs text-slate-100">
                            {prettyJson(currentTestEndpoint.sampleRequest ?? '{}')}
                          </pre>
                        </Card>
                      </Col>
                      <Col span={12}>
                        <Card size="small" title="样例响应">
                          <pre className="max-h-[220px] overflow-auto rounded-2xl bg-slate-950 p-3 text-xs text-slate-100">
                            {prettyJson(currentTestEndpoint.sampleResponse ?? '{}')}
                          </pre>
                        </Card>
                      </Col>
                    </Row>
                  ),
                },
              ]}
            />
          </>
        ) : null}
        <Form layout="vertical" form={testForm}>
          <Form.Item name="headers" label="请求头(JSON)">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="queryParams" label="Query 参数(JSON)">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="body" label="请求体(JSON)">
            <Input.TextArea rows={6} />
          </Form.Item>
          <Form.Item name="createdBy" label="发起人">
            <Input />
          </Form.Item>
        </Form>
        <Divider />
        <List
          size="small"
          header="联调说明"
          dataSource={[
            'GET 接口可以只填 Query 参数，POST/PUT/PATCH 再补请求体。',
            '如果认证配置已在接口源里填好，这里无需重复填写 Authorization。',
            '响应结果会直接写入右侧联调结果区域，并同时落一条测试日志。',
          ]}
          renderItem={(item) => <List.Item>{item}</List.Item>}
        />
      </Modal>
    </div>
  )
}
