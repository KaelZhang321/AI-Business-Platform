import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  message,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import ReactECharts from 'echarts-for-react'

import { uiBuilderApi } from '../api'
import { parseJsonInput, prettyJson } from '../helpers'

interface JsonRenderPlaygroundTabProps {
  initialValue?: string
}

interface JsonRenderElement {
  type: string
  props?: Record<string, unknown>
  children?: string[]
}

interface JsonRenderSpec {
  root: string
  elements: Record<string, JsonRenderElement>
}

interface JsonRenderPaginationAction {
  type?: string
  endpointId?: string
  roleId?: string
  flowNum?: string
  currentKey?: string
  sizeKey?: string
  requestTarget?: 'query' | 'body'
  queryParams?: Record<string, unknown>
  body?: Record<string, unknown>
}

interface JsonRenderPaginationConfig {
  current?: number
  pageSize?: number
  total?: number
  pages?: number
  mode?: string
  showSizeChanger?: boolean
  action?: JsonRenderPaginationAction
}

interface JsonRenderRowAction {
  key?: string
  label?: string
  type?: string
  detailEndpointId?: string
  submitEndpointId?: string
  idField?: string
  detailRequest?: Record<string, unknown>
}

interface JsonRenderFieldMapping {
  rowField?: string
  targetKey?: string
}

interface JsonRenderSubmitAction {
  endpointId?: string
  roleId?: string
  queryKeys?: string[]
  bodyKeys?: string[]
  headerKeys?: string[]
  staticQueryParams?: Record<string, unknown>
  staticBody?: Record<string, unknown>
  staticHeaders?: Record<string, unknown>
  useSampleWhenEmpty?: boolean
}

const DEFAULT_SPEC: JsonRenderSpec = {
  root: 'page',
  elements: {
    page: {
      type: 'Card',
      props: {
        title: 'json-render 预览示例',
        subtitle: '在左侧修改 JSON，右侧会按当前 spec 渲染页面',
      },
      children: ['statsCard', 'tableCard', 'listCard', 'formCard', 'chartCard'],
    },
    statsCard: {
      type: 'Card',
      props: { title: '核心指标' },
      children: ['metricRevenue', 'metricOrder'],
    },
    metricRevenue: {
      type: 'Metric',
      props: { label: '本月营收', value: 128000, format: 'currency' },
      children: [],
    },
    metricOrder: {
      type: 'Metric',
      props: { label: '订单数', value: 356, format: 'number' },
      children: [],
    },
    tableCard: {
      type: 'Table',
      props: {
        title: '销售榜单',
        columns: ['销售', '客户数', '成交额'],
        data: [
          ['张三', 18, 32000],
          ['李四', 15, 28000],
        ],
      },
      children: [],
    },
    listCard: {
      type: 'List',
      props: {
        title: '待处理事项',
        items: [
          {
            id: 'task-001',
            title: '审批采购申请',
            description: '等待主管审批新的设备采购申请',
            status: 'pending',
            assignee: '张三',
            dueDate: '2026-04-09',
            tags: [{ label: 'ERP', color: 'blue' }],
          },
        ],
        emptyText: '暂无待处理事项',
      },
      children: [],
    },
    formCard: {
      type: 'Form',
      props: {
        submitLabel: '提交筛选',
        fields: [
          { name: 'keyword', label: '关键词', type: 'text', placeholder: '输入关键字' },
          {
            name: 'system',
            label: '来源系统',
            type: 'select',
            options: [
              { label: '全部', value: 'all' },
              { label: 'ERP', value: 'erp' },
              { label: 'CRM', value: 'crm' },
            ],
          },
        ],
      },
      children: [],
    },
    chartCard: {
      type: 'Chart',
      props: {
        title: '近6个月成交趋势',
        kind: 'line',
        option: {
          tooltip: { trigger: 'axis' },
          xAxis: { type: 'category', data: ['10月', '11月', '12月', '1月', '2月', '3月'] },
          yAxis: { type: 'value' },
          series: [
            {
              name: '成交额',
              type: 'line',
              smooth: true,
              data: [82000, 91000, 87000, 105000, 119000, 128000],
            },
          ],
        },
      },
      children: [],
    },
  },
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isJsonRenderSpec(value: unknown): value is JsonRenderSpec {
  return isPlainObject(value)
    && typeof value.root === 'string'
    && isPlainObject(value.elements)
}

function patchSpecSubmitAction(spec: JsonRenderSpec, action: JsonRenderRowAction): JsonRenderSpec {
  if (!action.submitEndpointId) {
    return spec
  }

  const nextElements: Record<string, JsonRenderElement> = {}
  let changed = false

  for (const [elementId, element] of Object.entries(spec.elements)) {
    if (element.type !== 'Form' || !isPlainObject(element.props)) {
      nextElements[elementId] = element
      continue
    }

    const props = element.props
    if (isPlainObject(props.submitAction) && typeof props.submitAction.endpointId === 'string' && props.submitAction.endpointId) {
      nextElements[elementId] = element
      continue
    }

    const fieldKeys = toArray<Record<string, unknown>>(props.fields)
      .map((field) => {
        if (typeof field.standardKey === 'string' && field.standardKey) {
          return field.standardKey
        }
        if (typeof field.name === 'string' && field.name) {
          return field.name
        }
        return undefined
      })
      .filter((value): value is string => Boolean(value))

    nextElements[elementId] = {
      ...element,
      props: {
        ...props,
        submitAction: {
          endpointId: action.submitEndpointId,
          roleId: action.detailRequest && typeof action.detailRequest.roleId === 'string' ? action.detailRequest.roleId : undefined,
          bodyKeys: fieldKeys,
        },
      },
    }
    changed = true
  }

  return changed ? { ...spec, elements: nextElements } : spec
}

function formatMetricValue(value: unknown, format?: unknown) {
  if (typeof value !== 'number') {
    return String(value ?? '-')
  }
  if (format === 'currency') {
    return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(value)
  }
  if (format === 'percent') {
    return `${value}%`
  }
  return new Intl.NumberFormat('zh-CN').format(value)
}

function toArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : []
}

function buildTableColumns(
  columns: unknown,
  rowActions: JsonRenderRowAction[],
  onRowActionClick: (action: JsonRenderRowAction, record: Record<string, unknown>) => void,
): ColumnsType<Record<string, unknown>> {
  const baseColumns: ColumnsType<Record<string, unknown>> = toArray<unknown>(columns).map((column, index) => ({
    title: String(column),
    dataIndex: `col_${index}`,
    key: `col_${index}`,
    render: (value: unknown) => String(value ?? '-'),
  }))

  if (!rowActions.length) {
    return baseColumns
  }

  return [
    ...baseColumns,
    {
      title: '操作',
      key: 'actions',
      width: 180,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small" wrap>
          {rowActions.map((action, index) => (
            <Button
              key={`${action.key ?? action.label ?? 'action'}-${index}`}
              size="small"
              onClick={() => onRowActionClick(action, record)}
            >
              {String(action.label ?? action.key ?? '操作')}
            </Button>
          ))}
        </Space>
      ),
    },
  ]
}

function buildTableData(data: unknown, rowRecords?: unknown) {
  const rawRecords = toArray<Record<string, unknown>>(rowRecords)
  return toArray<unknown[]>(data).map((row, rowIndex) => {
    const record: Record<string, unknown> = { key: rowIndex }
    toArray<unknown>(row).forEach((cell, cellIndex) => {
      record[`col_${cellIndex}`] = cell
    })
    if (rawRecords[rowIndex]) {
      record.__rowRecord = rawRecords[rowIndex]
    }
    return record
  })
}

function JsonRenderTablePreview({
  title,
  props,
  onServerPaginate,
  onRowActionClick,
}: {
  title: string
  props: Record<string, unknown>
  onServerPaginate: (action: JsonRenderPaginationAction, nextPage: number, nextPageSize: number) => Promise<void>
  onRowActionClick: (action: JsonRenderRowAction, record: Record<string, unknown>) => void
}) {
  const paginationConfig = isPlainObject(props.pagination) ? (props.pagination as JsonRenderPaginationConfig) : undefined
  const initialCurrent = typeof paginationConfig?.current === 'number' ? paginationConfig.current : 1
  const [current, setCurrent] = useState(initialCurrent)
  const rowActions = toArray<Record<string, unknown>>(props.rowActions) as JsonRenderRowAction[]
  const columns = buildTableColumns(props.columns, rowActions, onRowActionClick)
  const dataSource = buildTableData(props.data, props.rowRecords)
  const pageSize = typeof paginationConfig?.pageSize === 'number' ? paginationConfig.pageSize : dataSource.length || 10
  const total = typeof paginationConfig?.total === 'number' ? paginationConfig.total : dataSource.length

  return (
    <Card title={title} className="rounded-[20px] shadow-sm">
      <Table
        rowKey="key"
        size="small"
        scroll={{ x: true }}
        columns={columns}
        dataSource={dataSource}
        pagination={paginationConfig ? {
          current,
          pageSize,
          total,
          showSizeChanger: paginationConfig.showSizeChanger === true,
          onChange: (page, nextPageSize) => {
            setCurrent(page)
            if (paginationConfig.mode === 'server' && paginationConfig.action?.endpointId) {
              void onServerPaginate(paginationConfig.action, page, nextPageSize ?? pageSize).catch(() => {
                setCurrent(initialCurrent)
              })
            }
          },
        } : false}
      />
      {paginationConfig?.mode === 'server' ? (
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          当前预览器会在翻页时重新调用后端 `/render` 接口刷新 spec。
        </Typography.Paragraph>
      ) : null}
    </Card>
  )
}

function renderField(field: Record<string, unknown>, editable = false) {
  const name = String(field.name ?? 'field')
  const label = String(field.label ?? name)
  const type = String(field.type ?? 'text')
  const placeholder = typeof field.placeholder === 'string' ? field.placeholder : undefined
  const readonly = field.readonly === true
  const disabled = !editable || readonly

  if (type === 'number') {
    return (
      <div key={name}>
        <Form.Item name={name} label={label}>
          <InputNumber className="w-full" disabled={disabled} placeholder={placeholder} />
        </Form.Item>
      </div>
    )
  }

  if (type === 'select') {
    const options = toArray<Record<string, unknown>>(field.options)
    return (
      <div key={name}>
        <Form.Item name={name} label={label}>
          <Select
            disabled={disabled}
            allowClear={!disabled}
            placeholder={placeholder ?? options.map((item) => item.label).filter(Boolean).join(' / ')}
            options={options.map((item) => ({
              label: String(item.label ?? item.value ?? ''),
              value: item.value,
            }))}
          />
        </Form.Item>
      </div>
    )
  }

  if (type === 'date') {
    return (
      <div key={name}>
        <Form.Item name={name} label={label}>
          <Input disabled={disabled} placeholder={placeholder ?? 'YYYY-MM-DD'} />
        </Form.Item>
      </div>
    )
  }

  return (
    <div key={name}>
      <Form.Item name={name} label={label}>
        <Input disabled={disabled} placeholder={placeholder} />
      </Form.Item>
    </div>
  )
}

function JsonRenderPreview({
  spec,
  onServerPaginate,
  onRowActionClick,
  editableForms,
  onFormSubmit,
  formSubmitting,
}: {
  spec: JsonRenderSpec
  onServerPaginate: (action: JsonRenderPaginationAction, nextPage: number, nextPageSize: number) => Promise<void>
  onRowActionClick: (action: JsonRenderRowAction, record: Record<string, unknown>) => void
  editableForms?: boolean
  onFormSubmit?: (submitAction: JsonRenderSubmitAction, values: Record<string, unknown>) => Promise<void>
  formSubmitting?: boolean
}) {
  const renderElement = (elementId: string): ReactNode => {
    const element = spec.elements[elementId]
    if (!element) {
      return (
        <Alert
          key={elementId}
          type="warning"
          showIcon
          message={`未找到节点：${elementId}`}
        />
      )
    }

    const props = isPlainObject(element.props) ? element.props : {}
    const children = toArray<string>(element.children).map((childId) => (
      <div key={childId}>{renderElement(childId)}</div>
    ))

    switch (element.type) {
      case 'Card':
        return (
          <Card
            title={typeof props.title === 'string' ? props.title : elementId}
            extra={typeof props.subtitle === 'string' ? <Typography.Text type="secondary">{props.subtitle}</Typography.Text> : undefined}
            className="rounded-[20px] shadow-sm"
            bodyStyle={{ display: 'flex', flexDirection: 'column', gap: 16 }}
          >
            {children.length ? children : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前卡片没有子节点" />}
          </Card>
        )

      case 'Metric':
        return (
          <Card size="small" className="rounded-[18px] border border-sky-100 bg-sky-50/50 shadow-none">
            <div className="text-xs uppercase tracking-[0.14em] text-slate-400">{String(props.label ?? elementId)}</div>
            <div className="mt-2 text-2xl font-semibold text-slate-900">{formatMetricValue(props.value, props.format)}</div>
          </Card>
        )

      case 'Table':
        return (
          <JsonRenderTablePreview
            title={typeof props.title === 'string' ? props.title : '表格'}
            props={props}
            onServerPaginate={onServerPaginate}
            onRowActionClick={onRowActionClick}
          />
        )

      case 'List':
        return (
          <Card title={typeof props.title === 'string' ? props.title : '列表'} className="rounded-[20px] shadow-sm">
            <List
              locale={{ emptyText: String(props.emptyText ?? '暂无数据') }}
              dataSource={toArray<Record<string, unknown>>(props.items)}
              renderItem={(item) => (
                <List.Item key={String(item.id ?? item.title ?? Math.random())}>
                  <div className="w-full space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <Typography.Text strong>{String(item.title ?? '-')}</Typography.Text>
                      <Space size={[4, 4]} wrap>
                        {toArray<Record<string, unknown>>(item.tags).map((tag, index) => (
                          <Tag key={`${item.id ?? item.title}-tag-${index}`} color={typeof tag.color === 'string' ? tag.color : 'default'}>
                            {String(tag.label ?? '-')}
                          </Tag>
                        ))}
                      </Space>
                    </div>
                    {item.description ? <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>{String(item.description)}</Typography.Paragraph> : null}
                    <Space size={16} wrap>
                      {item.status ? <Typography.Text type="secondary">状态：{String(item.status)}</Typography.Text> : null}
                      {item.assignee ? <Typography.Text type="secondary">处理人：{String(item.assignee)}</Typography.Text> : null}
                      {item.dueDate ? <Typography.Text type="secondary">截止：{String(item.dueDate)}</Typography.Text> : null}
                    </Space>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        )

      case 'Form':
        return (
          <Card title={typeof props.title === 'string' ? props.title : '表单'} className="rounded-[20px] shadow-sm">
            <Form
              layout="vertical"
              initialValues={isPlainObject(props.initialValues) ? props.initialValues : undefined}
              onFinish={(values) => {
                if (!editableForms || !isPlainObject(props.submitAction) || !onFormSubmit) {
                  return
                }
                void onFormSubmit(props.submitAction as JsonRenderSubmitAction, values as Record<string, unknown>)
              }}
            >
              {toArray<Record<string, unknown>>(props.fields).map((field) => renderField(field, editableForms === true))}
              <Button
                type="primary"
                htmlType="submit"
                loading={formSubmitting}
                disabled={!editableForms || !isPlainObject(props.submitAction)}
              >
                {String(props.submitLabel ?? '提交')}
              </Button>
            </Form>
          </Card>
        )

      case 'Tag':
        return (
          <Tag color={typeof props.color === 'string' ? props.color : 'blue'}>
            {String(props.label ?? elementId)}
          </Tag>
        )

      case 'Chart':
        return (
          <Card title={typeof props.title === 'string' ? props.title : '图表'} className="rounded-[20px] shadow-sm">
            {isPlainObject(props.option) ? (
              <ReactECharts
                option={props.option}
                notMerge
                style={{ height: 320, width: '100%' }}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前图表缺少 option 配置" />
            )}
          </Card>
        )

      default:
        return (
          <Alert
            type="warning"
            showIcon
            message={`暂不支持的节点类型：${element.type}`}
            description={`节点 ID：${elementId}`}
          />
        )
    }
  }

  return <div className="space-y-4">{renderElement(spec.root)}</div>
}

export function JsonRenderPlaygroundTab({ initialValue }: JsonRenderPlaygroundTabProps) {
  const [messageApi, contextHolder] = message.useMessage()
  const [input, setInput] = useState(initialValue ?? prettyJson(DEFAULT_SPEC))
  const [appliedInput, setAppliedInput] = useState(initialValue ?? prettyJson(DEFAULT_SPEC))
  const [runtimeSpec, setRuntimeSpec] = useState<JsonRenderSpec | null>(null)
  const [paging, setPaging] = useState(false)
  const [actionSpec, setActionSpec] = useState<JsonRenderSpec | null>(null)
  const [actionModalTitle, setActionModalTitle] = useState('操作预览')
  const [actionLoading, setActionLoading] = useState(false)
  const [formSubmitting, setFormSubmitting] = useState(false)

  const parsedResult = useMemo(() => {
    try {
      const parsed = parseJsonInput(appliedInput)
      if (!isJsonRenderSpec(parsed)) {
        return {
          spec: null,
          error: '当前 JSON 不是合法的 json-render 结构，必须包含 root 和 elements。',
        }
      }
      if (!parsed.elements[parsed.root]) {
        return {
          spec: null,
          error: `root 指向的节点不存在：${parsed.root}`,
        }
      }
      return { spec: parsed, error: null }
    } catch (error) {
      return {
        spec: null,
        error: error instanceof Error ? error.message : 'JSON 解析失败',
      }
    }
  }, [appliedInput])

  const activeSpec = runtimeSpec ?? parsedResult.spec

  async function handleServerPaginate(action: JsonRenderPaginationAction, nextPage: number, nextPageSize: number) {
    if (!action.endpointId) {
      return
    }
    const currentKey = typeof action.currentKey === 'string' ? action.currentKey : 'current'
    const sizeKey = typeof action.sizeKey === 'string' ? action.sizeKey : 'size'
    const requestTarget = action.requestTarget === 'body' ? 'body' : 'query'
    const nextQueryParams = {
      ...(isPlainObject(action.queryParams) ? action.queryParams : {}),
    }
    const nextBody = {
      ...(isPlainObject(action.body) ? action.body : {}),
    }

    if (requestTarget === 'body') {
      nextBody[currentKey] = nextPage
      nextBody[sizeKey] = nextPageSize
    } else {
      nextQueryParams[currentKey] = nextPage
      nextQueryParams[sizeKey] = nextPageSize
    }

    try {
      setPaging(true)
      const result = await uiBuilderApi.invokeEndpointAsJsonRender(action.endpointId, {
        roleId: action.roleId,
        flowNum: action.flowNum,
        queryParams: Object.keys(nextQueryParams).length ? nextQueryParams : undefined,
        body: Object.keys(nextBody).length ? nextBody : undefined,
      })
      const nextSpec = result.jsonRender
      if (!isJsonRenderSpec(nextSpec)) {
        throw new Error('后端返回的 json-render 结构不合法')
      }
      setRuntimeSpec(nextSpec)
      const nextText = prettyJson(nextSpec)
      setInput(nextText)
      setAppliedInput(nextText)
      messageApi.success(`已切换到第 ${nextPage} 页`)
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '分页请求失败')
      throw error
    } finally {
      setPaging(false)
    }
  }

  async function handleFormSubmit(submitAction: JsonRenderSubmitAction, values: Record<string, unknown>) {
    if (!submitAction.endpointId) {
      messageApi.warning('表单 submitAction 缺少 endpointId')
      return
    }
    try {
      setFormSubmitting(true)
      const result = await uiBuilderApi.submitJsonRenderForm({
        flowNum: `FLOW_FORM_${Date.now()}`,
        semanticValues: values,
        actions: [{
          endpointId: submitAction.endpointId,
          roleId: submitAction.roleId,
          queryKeys: Array.isArray(submitAction.queryKeys) ? submitAction.queryKeys : [],
          bodyKeys: Array.isArray(submitAction.bodyKeys) ? submitAction.bodyKeys : [],
          headerKeys: Array.isArray(submitAction.headerKeys) ? submitAction.headerKeys : [],
          staticQueryParams: isPlainObject(submitAction.staticQueryParams) ? submitAction.staticQueryParams : {},
          staticBody: isPlainObject(submitAction.staticBody) ? submitAction.staticBody : {},
          staticHeaders: isPlainObject(submitAction.staticHeaders) ? submitAction.staticHeaders : {},
          useSampleWhenEmpty: submitAction.useSampleWhenEmpty !== false,
        }],
      })
      messageApi.success(result.success ? '保存成功' : '保存失败')
      if (result.success) {
        setActionSpec(null)
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '表单提交失败')
    } finally {
      setFormSubmitting(false)
    }
  }

  async function handleRowActionClick(action: JsonRenderRowAction, record: Record<string, unknown>) {
    const actionName = String(action.label ?? action.key ?? '操作')
    const rowRecord = isPlainObject(record.__rowRecord) ? record.__rowRecord : undefined
    if (action.type === 'openFormModal') {
      if (!action.detailEndpointId) {
        messageApi.warning(`行操作“${actionName}”缺少 detailEndpointId`)
        return
      }
      if (!rowRecord) {
        messageApi.warning(`行操作“${actionName}”缺少 rowRecords，无法组装详情请求`)
        return
      }
      const detailRequest = isPlainObject(action.detailRequest) ? action.detailRequest : {}
      const requestTarget = detailRequest.requestTarget === 'body' ? 'body' : 'query'
      const fieldMappings = toArray<Record<string, unknown>>(detailRequest.fieldMappings) as JsonRenderFieldMapping[]
      const nextQueryParams = {
        ...(isPlainObject(detailRequest.queryParams) ? detailRequest.queryParams : {}),
      }
      const nextBody = {
        ...(isPlainObject(detailRequest.body) ? detailRequest.body : {}),
      }
      for (const mapping of fieldMappings) {
        const rowField = typeof mapping.rowField === 'string' ? mapping.rowField : undefined
        const targetKey = typeof mapping.targetKey === 'string' ? mapping.targetKey : rowField
        if (!rowField || !targetKey) {
          continue
        }
        const fieldValue = rowRecord[rowField]
        if (requestTarget === 'body') {
          nextBody[targetKey] = fieldValue
        } else {
          nextQueryParams[targetKey] = fieldValue
        }
      }

      try {
        setActionLoading(true)
        const result = await uiBuilderApi.invokeEndpointAsJsonRender(action.detailEndpointId, {
          queryParams: Object.keys(nextQueryParams).length ? nextQueryParams : undefined,
          body: Object.keys(nextBody).length ? nextBody : undefined,
        })
        if (!isJsonRenderSpec(result.jsonRender)) {
          throw new Error('详情接口返回的 json-render 结构不合法')
        }
        const nextActionSpec = patchSpecSubmitAction(result.jsonRender, action)
        setActionModalTitle(actionName)
        setActionSpec(nextActionSpec)
      } catch (error) {
        messageApi.error(error instanceof Error ? error.message : `行操作“${actionName}”执行失败`)
      } finally {
        setActionLoading(false)
      }
      return
    }
    messageApi.info(`已触发行操作：${actionName}`)
  }

  return (
    <div className="space-y-6">
      {contextHolder}
      <Card
        title="JSON Render 预览器"
        className="rounded-[24px]"
        extra={(
          <Space>
            <Button onClick={() => setInput(prettyJson(DEFAULT_SPEC))}>填充示例</Button>
            <Button
              onClick={() => {
                setRuntimeSpec(null)
                setAppliedInput(input)
              }}
            >
              应用预览
            </Button>
          </Space>
        )}
      >
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          左侧输入或粘贴 `json-render`，点击“应用预览”后，右侧直接按当前 spec 渲染页面。这个页签很适合验证后端生成结果和字段编排效果。
        </Typography.Paragraph>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(380px,520px)_minmax(0,1fr)]">
        <Card title="Spec 输入" className="rounded-[24px]">
          <Input.TextArea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            autoSize={{ minRows: 22, maxRows: 32 }}
            spellCheck={false}
            className="font-mono text-xs"
            placeholder="输入 json-render spec"
          />
        </Card>

        <Card title="页面预览" className="rounded-[24px]">
          {parsedResult.error ? (
            <Alert type="error" showIcon message="预览失败" description={parsedResult.error} />
          ) : activeSpec ? (
            <div className={paging ? 'pointer-events-none opacity-70' : undefined}>
              <JsonRenderPreview
                spec={activeSpec}
                onServerPaginate={handleServerPaginate}
                onRowActionClick={handleRowActionClick}
                editableForms={false}
                onFormSubmit={handleFormSubmit}
                formSubmitting={formSubmitting}
              />
            </div>
          ) : (
            <Empty description="输入 json-render 后即可预览" />
          )}
        </Card>
      </div>

      <Modal
        title={actionModalTitle}
        open={actionSpec != null}
        footer={null}
        width={960}
        onCancel={() => {
          if (actionLoading) {
            return
          }
          setActionSpec(null)
        }}
      >
        {actionSpec ? (
          <div className={actionLoading ? 'pointer-events-none opacity-70' : undefined}>
            <JsonRenderPreview
              spec={actionSpec}
              onServerPaginate={handleServerPaginate}
              onRowActionClick={handleRowActionClick}
              editableForms
              onFormSubmit={handleFormSubmit}
              formSubmitting={formSubmitting}
            />
          </div>
        ) : (
          <Empty description="暂无操作预览" />
        )}
      </Modal>
    </div>
  )
}
