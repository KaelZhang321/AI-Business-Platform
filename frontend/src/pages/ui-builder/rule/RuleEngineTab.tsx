import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  App,
  Button,
  Col,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Tabs,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  PlusOutlined,
  SaveOutlined,
} from '@ant-design/icons'

import { ruleApi } from './api'
import type {
  RuleCanvasEdge,
  RuleCanvasNode,
  RuleCanvasNodeType,
  RuleDataSourceOption,
  RuleEditorNodeFormValues,
  RuleRecord,
  RuleValidationRule,
} from './types'

const DEFAULT_PAGE_SIZE = 20

const NODE_TYPE_META: Array<{ type: RuleCanvasNodeType; label: string; description: string; backendType: string }> = [
  { type: 'input', label: '输入节点', description: '接收入参并做校验', backendType: 'INPUT_NODE' },
  { type: 'sql', label: 'SQL 节点', description: '执行 SQL 查询并输出结果', backendType: 'SQL_EXECUTE_NODE' },
  { type: 'parse', label: '解析节点', description: '解析上游结果并提取字段', backendType: 'PARSE_RESULT_NODE' },
  { type: 'calculate', label: '计算节点', description: '做表达式运算或派生字段', backendType: 'CALCULATE_NODE' },
  { type: 'output', label: '聚合节点', description: '聚合多个节点的输出结果', backendType: 'AGGREGATE_NODE' },
  { type: 'http', label: 'HTTP 节点', description: '调用外部接口并写回上下文', backendType: 'HTTP_REQUEST_NODE' },
]

const STATUS_META: Record<string, { color: string; label: string }> = {
  '0': { color: 'default', label: '草稿' },
  '1': { color: 'green', label: '启用' },
  '2': { color: 'orange', label: '停用' },
  '-1': { color: 'red', label: '删除' },
}

interface PanelProps {
  title?: ReactNode
  extra?: ReactNode
  className?: string
  children: ReactNode
}

function Panel({ title, extra, className, children }: PanelProps) {
  return (
    <section className={`min-w-0 overflow-hidden rounded-[24px] border border-slate-200 bg-white shadow-sm ${className ?? ''}`}>
      {(title || extra) ? (
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div className="text-base font-semibold text-slate-900">{title}</div>
          <div>{extra}</div>
        </div>
      ) : null}
      <div className="min-w-0 overflow-hidden p-6">{children}</div>
    </section>
  )
}

function createDefaultNodeFormValues(type: RuleCanvasNodeType, label?: string): RuleEditorNodeFormValues {
  return {
    label: label ?? NODE_TYPE_META.find((item) => item.type === type)?.label ?? '新节点',
    nodeGroup: 1,
    validationRules: type === 'input' ? [{ paramName: '', type: 'NOT_NULL', value: '' }] : [],
    nodeSql: '',
    dataSourceKey: '',
    resultKey: '',
    resultType: '',
    sourceKey: '',
    targetKey: '',
    parseType: '',
    columnName: '',
    filterColumnName: '',
    filterOperator: '',
    filterValue: '',
    operation: '',
    expression: '',
    variables: '',
    outputType: '',
    format: '',
    target: '',
    httpMethod: 'GET',
    url: '',
    timeout: 30,
    httpParams: [],
  }
}

function createNodeConfig(type: RuleCanvasNodeType, values: RuleEditorNodeFormValues) {
  switch (type) {
    case 'input':
      return { validationRules: values.validationRules }
    case 'sql':
      return {
        resultKey: values.resultKey,
        resultType: values.resultType,
        ...(values.dataSourceKey ? { dataSourceKey: values.dataSourceKey } : {}),
      }
    case 'parse':
      return {
        sourceKey: values.sourceKey,
        targetKey: values.targetKey,
        parseType: values.parseType,
        columnName: values.columnName,
        filterCondition: {
          columnName: values.filterColumnName,
          operator: values.filterOperator,
          value: values.filterValue,
        },
      }
    case 'calculate':
      return {
        operation: values.operation,
        expression: values.expression,
        variables: values.variables,
        resultKey: values.resultKey,
      }
    case 'output':
      return {
        outputType: values.outputType,
        format: values.format,
        target: values.target,
      }
    case 'http':
      return {
        httpMethod: values.httpMethod,
        url: values.url,
        timeout: values.timeout,
        httpParams: values.httpParams,
        resultKey: values.resultKey,
      }
    default:
      return {}
  }
}

function buildNodeParams(type: RuleCanvasNodeType, values: RuleEditorNodeFormValues) {
  const meta = NODE_TYPE_META.find((item) => item.type === type)
  return {
    label: values.label,
    nodeType: meta?.backendType ?? type,
    nodeGroup: values.nodeGroup,
    ...(type === 'sql' ? { nodeSql: values.nodeSql } : {}),
    nodeConfig: createNodeConfig(type, values),
  }
}

function extractNodeFormValues(node: RuleCanvasNode): RuleEditorNodeFormValues {
  const params = node.data.params
  const config = (params.nodeConfig ?? {}) as Record<string, unknown>
  const filterCondition = (config.filterCondition ?? {}) as Record<string, unknown>

  return {
    ...createDefaultNodeFormValues(node.type, params.label || node.data.label),
    label: params.label || node.data.label,
    nodeGroup: Number(params.nodeGroup ?? 1),
    validationRules: (config.validationRules as RuleValidationRule[] | undefined) ?? [],
    nodeSql: params.nodeSql,
    dataSourceKey: (config.dataSourceKey as string | undefined) ?? '',
    resultKey: (config.resultKey as string | undefined) ?? '',
    resultType: (config.resultType as string | undefined) ?? '',
    sourceKey: (config.sourceKey as string | undefined) ?? '',
    targetKey: (config.targetKey as string | undefined) ?? '',
    parseType: (config.parseType as string | undefined) ?? '',
    columnName: (config.columnName as string | undefined) ?? '',
    filterColumnName: (filterCondition.columnName as string | undefined) ?? '',
    filterOperator: (filterCondition.operator as string | undefined) ?? '',
    filterValue: (filterCondition.value as string | undefined) ?? '',
    operation: (config.operation as string | undefined) ?? '',
    expression: (config.expression as string | undefined) ?? '',
    variables: typeof config.variables === 'string' ? config.variables : JSON.stringify(config.variables ?? '', null, 2),
    outputType: (config.outputType as string | undefined) ?? '',
    format: typeof config.format === 'string' ? config.format : JSON.stringify(config.format ?? '', null, 2),
    target: (config.target as string | undefined) ?? '',
    httpMethod: ((config.httpMethod as RuleEditorNodeFormValues['httpMethod']) ?? 'GET'),
    url: (config.url as string | undefined) ?? '',
    timeout: Number(config.timeout ?? 30),
    httpParams: Array.isArray(config.httpParams) ? (config.httpParams as RuleEditorNodeFormValues['httpParams']) : [],
  }
}

function normalizeLoadedNodes(rule: RuleRecord): RuleCanvasNode[] {
  if (!rule.nodeDetail) {
    return []
  }
  try {
    const parsed = JSON.parse(rule.nodeDetail) as { nodes?: RuleCanvasNode[] }
    return Array.isArray(parsed.nodes) ? parsed.nodes : []
  } catch {
    return []
  }
}

function buildSequentialEdges(nodes: RuleCanvasNode[]): RuleCanvasEdge[] {
  return nodes.slice(1).map((node, index) => ({
    id: `e-${nodes[index]?.id}-${node.id}`,
    source: nodes[index]?.id,
    target: node.id,
    type: 'smoothstep',
    markerEnd: { type: 'arrowclosed', color: '#555' },
  }))
}

function parseJsonString(value?: string) {
  if (!value?.trim()) {
    return ''
  }
  try {
    return JSON.stringify(JSON.parse(value), null, 2)
  } catch {
    return value
  }
}

function formatDebugOutput(value: unknown) {
  if (value === undefined) {
    return 'undefined'
  }
  if (typeof value === 'string') {
    return value
  }
  try {
    const serialized = JSON.stringify(value, null, 2)
    return serialized ?? String(value)
  } catch {
    return String(value)
  }
}

function openRuleErrorModal(title: string, description: string) {
  Modal.error({
    title,
    content: description,
    width: 520,
  })
}

function applyRuleStatusLocally(
  ruleId: string,
  status: string | undefined,
  setRules: React.Dispatch<React.SetStateAction<RuleRecord[]>>,
  setSelectedRuleDetail: React.Dispatch<React.SetStateAction<RuleRecord | undefined>>,
) {
  setRules((prev) => prev.map((item) => (
    item.id === ruleId ? { ...item, status } : item
  )))
  setSelectedRuleDetail((prev) => (
    prev?.id === ruleId ? { ...prev, status } : prev
  ))
}

function applyRuleLocally(
  nextRule: RuleRecord,
  setRules: React.Dispatch<React.SetStateAction<RuleRecord[]>>,
  setSelectedRuleDetail: React.Dispatch<React.SetStateAction<RuleRecord | undefined>>,
) {
  if (!nextRule.id) {
    return
  }
  setRules((prev) => prev.map((item) => (
    item.id === nextRule.id ? { ...item, ...nextRule } : item
  )))
  setSelectedRuleDetail((prev) => (
    prev?.id === nextRule.id ? { ...prev, ...nextRule } : prev
  ))
}

export function RuleEngineTab() {
  const { message } = App.useApp()
  const [rules, setRules] = useState<RuleRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [debugging, setDebugging] = useState(false)
  const [togglingRuleId, setTogglingRuleId] = useState<string>()
  const [selectedRuleId, setSelectedRuleId] = useState<string>()
  const [selectedRuleDetail, setSelectedRuleDetail] = useState<RuleRecord>()
  const [selectedNodeId, setSelectedNodeId] = useState<string>()
  const [pagination, setPagination] = useState({ current: 1, pageSize: DEFAULT_PAGE_SIZE, total: 0 })
  const [createOpen, setCreateOpen] = useState(false)
  const [editingRuleId, setEditingRuleId] = useState<string>()
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugPayload, setDebugPayload] = useState('{\n  \n}')
  const [debugResult, setDebugResult] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [editorNodes, setEditorNodes] = useState<RuleCanvasNode[]>([])
  const [dataSources, setDataSources] = useState<RuleDataSourceOption[]>([])
  const [nodeForm] = Form.useForm<RuleEditorNodeFormValues>()
  const [createForm] = Form.useForm<Pick<RuleRecord, 'ruleName' | 'ruleCode' | 'description'>>()

  const selectedRule = useMemo(
    () => {
      if (selectedRuleDetail?.id === selectedRuleId) {
        return selectedRuleDetail
      }
      return rules.find((item) => item.id === selectedRuleId)
    },
    [rules, selectedRuleDetail, selectedRuleId],
  )
  const selectedNode = useMemo(
    () => editorNodes.find((item) => item.id === selectedNodeId),
    [editorNodes, selectedNodeId],
  )

  const ruleColumns: ColumnsType<RuleRecord> = [
    {
      title: '规则名称',
      dataIndex: 'ruleName',
      key: 'ruleName',
      render: (_, record) => (
        <button
          type="button"
          className="text-left font-medium text-sky-700 hover:text-sky-900"
          onClick={(event) => {
            event.stopPropagation()
            void handleSelectRule(record.id)
          }}
        >
          {record.ruleName}
        </button>
      ),
    },
    { title: '编码', dataIndex: 'ruleCode', key: 'ruleCode', width: 160 },
    { title: '版本', dataIndex: 'version', key: 'version', width: 100 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string | undefined) => {
        const meta = STATUS_META[status ?? '0'] ?? { color: 'default', label: status || '未知' }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '创建时间', dataIndex: 'createdTime', key: 'createdTime', width: 180 },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={(event) => {
              event.stopPropagation()
              void openEditRuleModal(record.id)
            }}
          >
            编辑
          </Button>
          <Button
            size="small"
            loading={togglingRuleId === record.id}
            onClick={(event) => {
              event.stopPropagation()
              void handleToggleStatus(record)
            }}
          >
            切换状态
          </Button>
          <Popconfirm title="确认删除当前规则？" onConfirm={() => void handleDeleteRule(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  useEffect(() => {
    void loadDataSources()
  }, [])

  useEffect(() => {
    void loadRules(pagination.current, pagination.pageSize)
  }, [pagination.current, pagination.pageSize])

  useEffect(() => {
    if (!selectedRule) {
      setEditorNodes([])
      setSelectedNodeId(undefined)
      return
    }
    const normalizedNodes = normalizeLoadedNodes(selectedRule)
    setEditorNodes(normalizedNodes)
    setSelectedNodeId(normalizedNodes[0]?.id)
  }, [selectedRule])

  useEffect(() => {
    if (!selectedNode) {
      nodeForm.resetFields()
      return
    }
    nodeForm.setFieldsValue(extractNodeFormValues(selectedNode))
  }, [selectedNode, nodeForm])

  async function loadRules(pageNo: number, pageSize: number) {
    setLoading(true)
    try {
      const response = await ruleApi.listRules({ pageNo, pageSize })
      if (response.success) {
        const records = response.data.records ?? []
        setRules(records)
        setPagination((prev) => ({
          ...prev,
          current: Number(response.data.current) || 1,
          pageSize: Number(response.data.size) || DEFAULT_PAGE_SIZE,
          total: Number(response.data.total) || 0,
        }))
        if (!records.length) {
          setSelectedRuleId(undefined)
          setSelectedRuleDetail(undefined)
          return
        }
        const nextSelectedRuleId = records.some((item) => item.id === selectedRuleId)
          ? selectedRuleId
          : records[0]?.id
        if (nextSelectedRuleId !== selectedRuleId) {
          setSelectedRuleId(nextSelectedRuleId)
        }
        const matchedRule = records.find((item) => item.id === nextSelectedRuleId)
        if (matchedRule) {
          setSelectedRuleDetail((prev) => (prev?.id === matchedRule.id ? { ...prev, ...matchedRule } : prev))
        }
      } else {
        message.error(response.message || '加载规则列表失败')
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载规则列表失败')
    } finally {
      setLoading(false)
    }
  }

  async function loadDataSources() {
    try {
      const response = await ruleApi.listDataSources()
      if (!response.success) {
        message.error(response.message || '加载数据源列表失败')
        return
      }
      setDataSources(response.data ?? [])
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载数据源列表失败')
    }
  }

  async function handleCreateRule() {
    const values = await createForm.validateFields()
    if (editingRuleId && selectedRule?.status === '1') {
      openRuleErrorModal('当前规则不可编辑', '激活状态的规则不允许修改，请先切换为草稿或停用后再编辑。')
      return
    }
    setSaving(true)
    try {
      const response = await ruleApi.saveOrUpdateRule({
        ...(editingRuleId ? {
          id: editingRuleId,
          nodeDetail: selectedRule?.nodeDetail,
          version: selectedRule?.version,
          status: selectedRule?.status,
        } : {}),
        ruleName: values.ruleName,
        ruleCode: values.ruleCode,
        description: values.description,
      })
      if (!response.success) {
        openRuleErrorModal(editingRuleId ? '更新规则失败' : '创建规则失败', response.message || '规则保存失败')
        message.error(response.message || '创建规则失败')
        return
      }
      setCreateOpen(false)
      setEditingRuleId(undefined)
      createForm.resetFields()
      message.success(editingRuleId ? '规则已更新' : '规则创建成功')
      await loadRules(1, pagination.pageSize)
      if (response.data?.id) {
        await handleSelectRule(response.data.id, true)
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : (editingRuleId ? '更新规则失败' : '创建规则失败'))
    } finally {
      setSaving(false)
    }
  }

  async function handleSelectRule(ruleId?: string, silent = false) {
    if (!ruleId) {
      return
    }
    try {
      const response = await ruleApi.getRuleById(ruleId)
      if (!response.success) {
        if (!silent) {
          message.error(response.message || '加载规则详情失败')
        }
        return
      }
      const nextRuleId = response.data.id ?? ruleId
      setSelectedRuleId(nextRuleId)
      setSelectedRuleDetail(response.data)
      setRules((prev) => prev.map((item) => (item.id === nextRuleId ? { ...item, ...response.data } : item)))
    } catch (error) {
      if (!silent) {
        message.error(error instanceof Error ? error.message : '加载规则详情失败')
      }
    }
  }

  async function openEditRuleModal(ruleId?: string) {
    if (!ruleId) {
      return
    }
    try {
      const response = await ruleApi.getRuleById(ruleId)
      if (!response.success) {
        message.error(response.message || '加载规则详情失败')
        return
      }
      const detail = response.data
      const nextRuleId = detail.id ?? ruleId
      setSelectedRuleId(nextRuleId)
      setSelectedRuleDetail(detail)
      setRules((prev) => prev.map((item) => (item.id === nextRuleId ? { ...item, ...detail } : item)))
      createForm.setFieldsValue({
        ruleName: detail.ruleName,
        ruleCode: detail.ruleCode,
        description: detail.description,
      })
      setEditingRuleId(nextRuleId)
      setCreateOpen(true)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载规则详情失败')
    }
  }

  async function handleDeleteRule(ruleId?: string) {
    if (!ruleId) {
      return
    }
    try {
      const response = await ruleApi.deleteRule(ruleId)
      if (!response.success) {
        message.error(response.message || '删除规则失败')
        return
      }
      message.success('规则已删除')
      if (selectedRuleId === ruleId) {
        setSelectedRuleId(undefined)
        setSelectedRuleDetail(undefined)
      }
      await loadRules(pagination.current, pagination.pageSize)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '删除规则失败')
    }
  }

  async function handleToggleStatus(rule: RuleRecord) {
    if (!rule.id) {
      return
    }
    const nextStatus = rule.status === '1' ? '0' : '1'
    setTogglingRuleId(rule.id)
    try {
      applyRuleStatusLocally(rule.id, nextStatus, setRules, setSelectedRuleDetail)

      const response = await ruleApi.enableRule(rule.id)
      if (!response.success) {
        applyRuleStatusLocally(rule.id, rule.status, setRules, setSelectedRuleDetail)
        message.error(response.message || '切换状态失败')
        return
      }
      if (response.data?.id) {
        applyRuleLocally(response.data, setRules, setSelectedRuleDetail)
      } else {
        applyRuleStatusLocally(rule.id, nextStatus, setRules, setSelectedRuleDetail)
      }
      message.success('规则状态已切换')
      await loadRules(pagination.current, pagination.pageSize)
      if (selectedRuleId === rule.id) {
        await handleSelectRule(rule.id, true)
      }
    } catch (error) {
      applyRuleStatusLocally(rule.id, rule.status, setRules, setSelectedRuleDetail)
      message.error(error instanceof Error ? error.message : '切换状态失败')
    } finally {
      setTogglingRuleId(undefined)
    }
  }

  function handleAddNode(type: RuleCanvasNodeType) {
    const index = editorNodes.filter((item) => item.type === type).length + 1
    const meta = NODE_TYPE_META.find((item) => item.type === type)
    const node: RuleCanvasNode = {
      id: `${type}-${Date.now()}`,
      type,
      position: { x: 0, y: editorNodes.length * 80 },
      data: {
        label: `${meta?.label ?? type}${index}`,
        params: buildNodeParams(type, createDefaultNodeFormValues(type, `${meta?.label ?? type}${index}`)),
      },
    }
    setEditorNodes((prev) => [...prev, node])
    setSelectedNodeId(node.id)
    message.success('节点已添加')
  }

  async function handleSaveNodeParams() {
    if (!selectedNode) {
      return
    }
    const values = await nodeForm.validateFields()
    const nextParams = buildNodeParams(selectedNode.type, values)
    setEditorNodes((prev) => prev.map((item) => (
      item.id === selectedNode.id
        ? { ...item, data: { ...item.data, label: values.label, params: nextParams } }
        : item
    )))
    message.success('节点参数已保存')
  }

  function handleMoveNode(nodeId: string, direction: 'up' | 'down') {
    setEditorNodes((prev) => {
      const index = prev.findIndex((item) => item.id === nodeId)
      if (index < 0) {
        return prev
      }
      const targetIndex = direction === 'up' ? index - 1 : index + 1
      if (targetIndex < 0 || targetIndex >= prev.length) {
        return prev
      }
      const next = [...prev]
      ;[next[index], next[targetIndex]] = [next[targetIndex], next[index]]
      return next.map((item, currentIndex) => ({
        ...item,
        position: { x: 0, y: currentIndex * 80 },
      }))
    })
  }

  function handleDeleteNode(nodeId: string) {
    setEditorNodes((prev) => prev.filter((item) => item.id !== nodeId))
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(undefined)
    }
  }

  async function handleSaveRule() {
    if (!selectedRule) {
      message.warning('请先选择一条规则')
      return
    }
    if (selectedRule.status === '1') {
      openRuleErrorModal('当前规则不可保存', '激活状态的规则不允许修改，请先切换为草稿或停用后再保存。')
      return
    }
    setSaving(true)
    try {
      const normalizedNodes = editorNodes.map((node, index) => ({
        ...node,
        position: { x: 0, y: index * 80 },
      }))
      const nodeDetail = JSON.stringify({
        nodes: normalizedNodes,
        edges: buildSequentialEdges(normalizedNodes),
        timestamp: new Date().toISOString(),
      })
      const response = await ruleApi.saveOrUpdateRule({
        id: selectedRule.id,
        ruleName: selectedRule.ruleName,
        ruleCode: selectedRule.ruleCode,
        version: selectedRule.version,
        status: selectedRule.status,
        description: selectedRule.description,
        nodeDetail,
      })
      if (!response.success) {
        openRuleErrorModal('保存规则失败', response.message || '规则保存失败')
        message.error(response.message || '保存规则失败')
        return
      }
      message.success('规则已保存')
      await loadRules(pagination.current, pagination.pageSize)
      if (response.data?.id) {
        await handleSelectRule(response.data.id, true)
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存规则失败')
    } finally {
      setSaving(false)
    }
  }

  function openDebugModal() {
    setDebugPayload('{\n  \n}')
    setDebugResult('')
    setDebugOpen(true)
  }

  async function handleExecuteRule() {
    if (!selectedRule?.ruleCode) {
      message.warning('当前规则缺少规则编码，暂时无法调试')
      return
    }
    const version = Number(selectedRule.version || 1)
    if (!Number.isFinite(version)) {
      message.warning('当前规则版本不合法，暂时无法调试')
      return
    }

    let parsedPayload: Record<string, unknown>
    try {
      const raw = debugPayload.trim()
      parsedPayload = raw ? JSON.parse(raw) as Record<string, unknown> : {}
    } catch (error) {
      message.error(error instanceof Error ? `调试参数不是合法 JSON: ${error.message}` : '调试参数不是合法 JSON')
      return
    }

    setDebugging(true)
    try {
      const response = await ruleApi.executeRule(selectedRule.ruleCode, version, parsedPayload)
      setDebugResult(formatDebugOutput(response))
      if (!response.success) {
        message.error(response.message || '规则调试失败')
        return
      }
      message.success('规则调试完成')
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '规则调试失败'
      setDebugResult(formatDebugOutput({ success: false, message: errorMessage }))
      message.error(errorMessage)
    } finally {
      setDebugging(false)
    }
  }

  const previewJson = useMemo(() => JSON.stringify({
    nodes: editorNodes,
    edges: buildSequentialEdges(editorNodes),
    timestamp: new Date().toISOString(),
  }, null, 2), [editorNodes])

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border border-slate-200/80 bg-white px-8 py-8 shadow-sm">
        <Space direction="vertical" size={10}>
          <Typography.Text type="secondary">规则编排 / 可视配置</Typography.Text>
          <Typography.Title level={2} style={{ margin: 0 }}>
            规则引擎工作台
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0, maxWidth: 920 }}>
            React 版规则引擎编辑器保留了原先的规则列表、节点编排、参数编辑和 JSON 预览能力，但改成了更适合当前栈的列表式配置，不再依赖 Vue Flow。
          </Typography.Paragraph>
        </Space>
      </section>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={9} className="min-w-0">
          <Panel
            className=""
            title="规则列表"
            extra={(
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  setEditingRuleId(undefined)
                  createForm.resetFields()
                  setCreateOpen(true)
                }}
              >
                新建规则
              </Button>
            )}
          >
            <Table
              className="[&_.ant-table-container]:overflow-x-auto"
              rowKey="id"
              loading={loading}
              columns={ruleColumns}
              dataSource={rules}
              size="middle"
              scroll={{ x: 980 }}
              pagination={{
                current: pagination.current,
                pageSize: pagination.pageSize,
                total: pagination.total,
                showSizeChanger: true,
                onChange: (page, pageSize) => setPagination((prev) => ({ ...prev, current: page, pageSize: pageSize ?? prev.pageSize })),
              }}
              rowClassName={(record) => (
                record.id === selectedRuleId ? 'bg-sky-50' : ''
              )}
              onRow={(record) => ({
                onClick: () => void handleSelectRule(record.id),
              })}
            />
          </Panel>
        </Col>

        <Col xs={24} xl={15} className="min-w-0">
          <div className="space-y-4">
            <Panel
              title={selectedRule ? `当前规则 · ${selectedRule.ruleName}` : '规则信息'}
              extra={(
                <Space>
                  <Button onClick={openDebugModal} disabled={!selectedRule}>
                    调试规则
                  </Button>
                  <Button icon={<EyeOutlined />} onClick={() => setPreviewOpen(true)} disabled={!selectedRule}>
                    预览 JSON
                  </Button>
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    onClick={() => void handleSaveRule()}
                    disabled={!selectedRule || selectedRule.status === '1'}
                    loading={saving}
                  >
                    保存规则
                  </Button>
                </Space>
              )}
            >
              {!selectedRule ? (
                <Empty description="左侧选择规则后，这里会显示规则详情和节点编辑器" />
              ) : (
                <div className="space-y-4">
                  {selectedRule.status === '1' ? (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                      当前规则处于启用状态，后端禁止直接修改。请先点击“切换状态”改为草稿或停用，再保存节点编排。
                    </div>
                  ) : null}
                  <div className="flex flex-wrap items-center gap-x-10 gap-y-3 text-sm text-slate-600">
                    <div>
                      <span className="mr-2 text-slate-400">规则编码:</span>
                      <span className="font-medium text-slate-900">{selectedRule.ruleCode || '-'}</span>
                    </div>
                    <div>
                      <span className="mr-2 text-slate-400">版本:</span>
                      <span className="font-medium text-slate-900">{selectedRule.version || '-'}</span>
                    </div>
                    <div className="flex items-center">
                      <span className="mr-2 text-slate-400">状态:</span>
                      <Tag color={STATUS_META[selectedRule.status ?? '0']?.color ?? 'default'}>
                        {STATUS_META[selectedRule.status ?? '0']?.label ?? (selectedRule.status || '-')}
                      </Tag>
                    </div>
                    <div>
                      <span className="mr-2 text-slate-400">更新时间:</span>
                      <span className="font-medium text-slate-900">{selectedRule.updatedTime ?? selectedRule.createdTime ?? '-'}</span>
                    </div>
                  </div>
                </div>
              )}
            </Panel>

            {selectedRule ? (
              <Row gutter={[16, 16]}>
                <Col xs={24} lg={9}>
                  <Panel
                    className="h-full"
                    title="节点编排"
                    extra={(
                      <Select
                        placeholder="添加节点"
                        style={{ width: 150 }}
                        onSelect={(value) => handleAddNode(value as RuleCanvasNodeType)}
                        options={NODE_TYPE_META.map((item) => ({ value: item.type, label: item.label }))}
                      />
                    )}
                  >
                    {editorNodes.length === 0 ? (
                      <Empty description="还没有节点，先从右上角添加一个" />
                    ) : (
                      <List<RuleCanvasNode>
                        dataSource={editorNodes}
                        renderItem={(node, index) => {
                          const meta = NODE_TYPE_META.find((item) => item.type === node.type)
                          const nodeGroup = node.data.params.nodeGroup
                          return (
                            <List.Item
                              className={`cursor-pointer rounded-2xl border px-3 py-3 ${node.id === selectedNodeId ? 'border-sky-300 bg-sky-50' : 'border-slate-200 bg-white'}`}
                              onClick={() => setSelectedNodeId(node.id)}
                              actions={[
                                <Button key="up" type="text" icon={<ArrowUpOutlined />} disabled={index === 0} onClick={(event) => {
                                  event.stopPropagation()
                                  handleMoveNode(node.id, 'up')
                                }} />,
                                <Button key="down" type="text" icon={<ArrowDownOutlined />} disabled={index === editorNodes.length - 1} onClick={(event) => {
                                  event.stopPropagation()
                                  handleMoveNode(node.id, 'down')
                                }} />,
                                <Button key="delete" type="text" danger icon={<DeleteOutlined />} onClick={(event) => {
                                  event.stopPropagation()
                                  handleDeleteNode(node.id)
                                }} />,
                              ]}
                            >
                              <List.Item.Meta
                                title={(
                                  <Space>
                                    <span>{node.data.label}</span>
                                    <Tag color="blue">{meta?.label ?? node.type}</Tag>
                                  </Space>
                                )}
                                description={(
                                  <Space size={12} wrap>
                                    <span>ID: {node.id}</span>
                                    <span>分组: {nodeGroup}</span>
                                  </Space>
                                )}
                              />
                            </List.Item>
                          )
                        }}
                      />
                    )}
                  </Panel>
                </Col>

                <Col xs={24} lg={15}>
                  <Tabs
                    items={[
                      {
                        key: 'editor',
                        label: '节点参数',
                        children: selectedNode ? (
                          <Panel title={selectedNode.data.label}>
                            <Form form={nodeForm} layout="vertical">
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item name="label" label="节点名称" rules={[{ required: true, message: '请输入节点名称' }]}>
                                    <Input />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item name="nodeGroup" label="节点分组" rules={[{ required: true, message: '请输入节点分组' }]}>
                                    <InputNumber min={1} style={{ width: '100%' }} />
                                  </Form.Item>
                                </Col>
                              </Row>

                              {selectedNode.type === 'input' ? (
                                <Form.List name="validationRules">
                                  {(fields, { add, remove }) => (
                                    <div className="space-y-3">
                                      {fields.map((field) => (
                                        <div key={field.key} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                          <Row gutter={12}>
                                            <Col span={8}>
                                              <Form.Item {...field} name={[field.name, 'paramName']} label="参数名" rules={[{ required: true, message: '请输入参数名' }]}>
                                                <Input />
                                              </Form.Item>
                                            </Col>
                                            <Col span={8}>
                                              <Form.Item {...field} name={[field.name, 'type']} label="校验类型" rules={[{ required: true, message: '请选择类型' }]}>
                                                <Select options={[
                                                  { value: 'NULL', label: 'NULL' },
                                                  { value: 'NOT_NULL', label: 'NOT_NULL' },
                                                  { value: 'REGEX', label: 'REGEX' },
                                                  { value: 'RANGE', label: 'RANGE' },
                                                ]} />
                                              </Form.Item>
                                            </Col>
                                            <Col span={6}>
                                              <Form.Item {...field} name={[field.name, 'value']} label="校验值">
                                                <Input />
                                              </Form.Item>
                                            </Col>
                                            <Col span={2} className="pt-8">
                                              <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(field.name)} />
                                            </Col>
                                          </Row>
                                        </div>
                                      ))}
                                      <Button onClick={() => add({ paramName: '', type: 'NOT_NULL', value: '' })}>添加校验规则</Button>
                                    </div>
                                  )}
                                </Form.List>
                              ) : null}

                              {selectedNode.type === 'sql' ? (
                                <>
                                  <Form.Item name="nodeSql" label="SQL 语句" rules={[{ required: true, message: '请输入 SQL 语句' }]}>
                                    <Input.TextArea rows={6} />
                                  </Form.Item>
                                  <Row gutter={16}>
                                    <Col span={12}>
                                      <Form.Item name="dataSourceKey" label="执行数据源">
                                        <Select
                                          allowClear
                                          placeholder="不选则使用默认数据源"
                                          options={dataSources.map((item) => ({
                                            label: item.defaultSelected ? `${item.label}（默认）` : item.label,
                                            value: item.key,
                                          }))}
                                        />
                                      </Form.Item>
                                    </Col>
                                    <Col span={12}>
                                      <Form.Item name="resultKey" label="结果 Key">
                                        <Input />
                                      </Form.Item>
                                    </Col>
                                  </Row>
                                  <Row gutter={16}>
                                    <Col span={12}>
                                      <Form.Item name="resultType" label="结果类型" rules={[{ required: true, message: '请选择结果类型' }]}>
                                        <Select options={[
                                          { value: 'LIST', label: 'LIST' },
                                          { value: 'SINGLE_VALUE', label: 'SINGLE_VALUE' },
                                          { value: 'SINGLE_ROW', label: 'SINGLE_ROW' },
                                        ]} />
                                      </Form.Item>
                                    </Col>
                                  </Row>
                                </>
                              ) : null}

                              {selectedNode.type === 'parse' ? (
                                <>
                                  <Row gutter={16}>
                                    <Col span={12}>
                                      <Form.Item name="sourceKey" label="上游参数 Key" rules={[{ required: true, message: '请输入上游参数 Key' }]}>
                                        <Input />
                                      </Form.Item>
                                    </Col>
                                    <Col span={12}>
                                      <Form.Item name="targetKey" label="目标参数 Key" rules={[{ required: true, message: '请输入目标参数 Key' }]}>
                                        <Input />
                                      </Form.Item>
                                    </Col>
                                  </Row>
                                  <Row gutter={16}>
                                    <Col span={12}>
                                      <Form.Item name="parseType" label="解析类型" rules={[{ required: true, message: '请选择解析类型' }]}>
                                        <Select options={[
                                          { value: 'TO_LIST', label: 'TO_LIST' },
                                          { value: 'TO_STRING_ARRAY', label: 'TO_STRING_ARRAY' },
                                          { value: 'TO_MAP_LIST', label: 'TO_MAP_LIST' },
                                          { value: 'EXTRACT_COLUMN', label: 'EXTRACT_COLUMN' },
                                        ]} />
                                      </Form.Item>
                                    </Col>
                                    <Col span={12}>
                                      <Form.Item name="columnName" label="列名">
                                        <Input />
                                      </Form.Item>
                                    </Col>
                                  </Row>
                                  <Row gutter={16}>
                                    <Col span={8}>
                                      <Form.Item name="filterColumnName" label="过滤列">
                                        <Input />
                                      </Form.Item>
                                    </Col>
                                    <Col span={8}>
                                      <Form.Item name="filterOperator" label="操作符">
                                        <Select options={[
                                          { value: 'EQUALS', label: 'EQUALS' },
                                          { value: 'LIKE', label: 'LIKE' },
                                          { value: 'IN', label: 'IN' },
                                        ]} />
                                      </Form.Item>
                                    </Col>
                                    <Col span={8}>
                                      <Form.Item name="filterValue" label="过滤值">
                                        <Input />
                                      </Form.Item>
                                    </Col>
                                  </Row>
                                </>
                              ) : null}

                              {selectedNode.type === 'calculate' ? (
                                <>
                                  <Row gutter={16}>
                                    <Col span={12}>
                                      <Form.Item name="operation" label="运算类型" rules={[{ required: true, message: '请选择运算类型' }]}>
                                        <Select options={[
                                          { value: 'ADD', label: 'ADD' },
                                          { value: 'SUBTRACT', label: 'SUBTRACT' },
                                          { value: 'MULTIPLY', label: 'MULTIPLY' },
                                          { value: 'DIVIDE', label: 'DIVIDE' },
                                          { value: 'CUSTOM', label: 'CUSTOM' },
                                        ]} />
                                      </Form.Item>
                                    </Col>
                                    <Col span={12}>
                                      <Form.Item name="resultKey" label="结果 Key">
                                        <Input />
                                      </Form.Item>
                                    </Col>
                                  </Row>
                                  <Form.Item name="expression" label="计算表达式" rules={[{ required: true, message: '请输入表达式' }]}>
                                    <Input.TextArea rows={4} />
                                  </Form.Item>
                                  <Form.Item name="variables" label="变量映射(JSON)">
                                    <Input.TextArea rows={4} />
                                  </Form.Item>
                                </>
                              ) : null}

                              {selectedNode.type === 'output' ? (
                                <>
                                  <Row gutter={16}>
                                    <Col span={12}>
                                      <Form.Item name="outputType" label="输出类型" rules={[{ required: true, message: '请选择输出类型' }]}>
                                        <Select options={[
                                          { value: 'JSON', label: 'JSON' },
                                          { value: 'TEXT', label: 'TEXT' },
                                          { value: 'FILE', label: 'FILE' },
                                          { value: 'API', label: 'API' },
                                        ]} />
                                      </Form.Item>
                                    </Col>
                                    <Col span={12}>
                                      <Form.Item name="target" label="目标位置">
                                        <Input />
                                      </Form.Item>
                                    </Col>
                                  </Row>
                                  <Form.Item name="format" label="输出格式(JSON 或模板)">
                                    <Input.TextArea rows={5} />
                                  </Form.Item>
                                </>
                              ) : null}

                              {selectedNode.type === 'http' ? (
                                <>
                                  <Row gutter={16}>
                                    <Col span={8}>
                                      <Form.Item name="httpMethod" label="请求方式">
                                        <Select options={[
                                          { value: 'GET', label: 'GET' },
                                          { value: 'POST', label: 'POST' },
                                          { value: 'PUT', label: 'PUT' },
                                          { value: 'DELETE', label: 'DELETE' },
                                          { value: 'PATCH', label: 'PATCH' },
                                        ]} />
                                      </Form.Item>
                                    </Col>
                                    <Col span={10}>
                                      <Form.Item name="timeout" label="超时(秒)">
                                        <InputNumber min={1} style={{ width: '100%' }} />
                                      </Form.Item>
                                    </Col>
                                    <Col span={6}>
                                      <Form.Item name="resultKey" label="结果 Key">
                                        <Input />
                                      </Form.Item>
                                    </Col>
                                  </Row>
                                  <Form.Item name="url" label="请求地址" rules={[{ required: true, message: '请输入请求地址' }]}>
                                    <Input />
                                  </Form.Item>
                                  <Form.List name="httpParams">
                                    {(fields, { add, remove }) => (
                                      <div className="space-y-3">
                                        {fields.map((field) => (
                                          <div key={field.key} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                            <Row gutter={12}>
                                              <Col span={8}>
                                                <Form.Item {...field} name={[field.name, 'sourceParam']} label="输入源参数" rules={[{ required: true, message: '请输入输入源参数' }]}>
                                                  <Input />
                                                </Form.Item>
                                              </Col>
                                              <Col span={8}>
                                                <Form.Item {...field} name={[field.name, 'paramType']} label="参数类型" rules={[{ required: true, message: '请选择参数类型' }]}>
                                                  <Select options={[
                                                    { value: 'query', label: 'query' },
                                                    { value: 'header', label: 'header' },
                                                    { value: 'body', label: 'body' },
                                                  ]} />
                                                </Form.Item>
                                              </Col>
                                              <Col span={6}>
                                                <Form.Item {...field} name={[field.name, 'targetKey']} label="目标 Key" rules={[{ required: true, message: '请输入目标 Key' }]}>
                                                  <Input />
                                                </Form.Item>
                                              </Col>
                                              <Col span={2} className="pt-8">
                                                <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(field.name)} />
                                              </Col>
                                            </Row>
                                          </div>
                                        ))}
                                        <Button onClick={() => add({ sourceParam: '', paramType: 'query', targetKey: '' })}>添加请求参数</Button>
                                      </div>
                                    )}
                                  </Form.List>
                                </>
                              ) : null}

                              <div className="mt-6 flex justify-end">
                                <Button type="primary" onClick={() => void handleSaveNodeParams()}>
                                  保存节点参数
                                </Button>
                              </div>
                            </Form>
                          </Panel>
                        ) : (
                          <Panel>
                            <Empty description="先从左侧选择一个节点，再编辑它的参数" />
                          </Panel>
                        ),
                      },
                      {
                        key: 'summary',
                        label: '执行视图',
                        children: (
                          <Panel title="当前执行顺序">
                            {editorNodes.length === 0 ? (
                              <Empty description="还没有节点" />
                            ) : (
                              <List<RuleCanvasNode>
                                dataSource={editorNodes}
                                renderItem={(node, index) => {
                                  const meta = NODE_TYPE_META.find((item) => item.type === node.type)
                                  return (
                                    <List.Item>
                                      <List.Item.Meta
                                        title={`${index + 1}. ${node.data.label}`}
                                        description={`${meta?.label ?? node.type} / 分组 ${node.data.params.nodeGroup}`}
                                      />
                                    </List.Item>
                                  )
                                }}
                              />
                            )}
                          </Panel>
                        ),
                      },
                    ]}
                  />
                </Col>
              </Row>
            ) : null}
          </div>
        </Col>
      </Row>

      <Modal
        title={editingRuleId ? '编辑规则' : '新建规则'}
        open={createOpen}
        onCancel={() => {
          setCreateOpen(false)
          setEditingRuleId(undefined)
          createForm.resetFields()
        }}
        onOk={() => void handleCreateRule()}
        confirmLoading={saving}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="ruleName" label="规则名称" rules={[{ required: true, message: '请输入规则名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="ruleCode" label="规则编码" rules={[{ required: true, message: '请输入规则编码' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title="规则 JSON 预览"
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        width={720}
      >
        <Tabs
          items={[
            {
              key: 'nodeDetail',
              label: 'nodeDetail',
              children: (
                <pre className="max-h-[70vh] overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-100">
                  {previewJson}
                </pre>
              ),
            },
            {
              key: 'currentRule',
              label: '规则对象',
              children: (
                <pre className="max-h-[70vh] overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-100">
                  {JSON.stringify({
                    ...selectedRule,
                    nodeDetail: parseJsonString(previewJson),
                  }, null, 2)}
                </pre>
              ),
            },
          ]}
        />
      </Drawer>

      <Modal
        title={selectedRule ? `调试规则 · ${selectedRule.ruleName}` : '调试规则'}
        open={debugOpen}
        onCancel={() => {
          if (!debugging) {
            setDebugOpen(false)
          }
        }}
        onOk={() => void handleExecuteRule()}
        confirmLoading={debugging}
        okText="执行调试"
        width={860}
      >
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <div>
              <span className="mr-2 text-slate-400">规则编码:</span>
              <span className="font-medium text-slate-900">{selectedRule?.ruleCode || '-'}</span>
            </div>
            <div className="mt-2">
              <span className="mr-2 text-slate-400">版本:</span>
              <span className="font-medium text-slate-900">{selectedRule?.version || '1'}</span>
            </div>
          </div>
          <div>
            <div className="mb-2 text-sm font-medium text-slate-900">调试入参(JSON)</div>
            <Input.TextArea
              rows={10}
              value={debugPayload}
              onChange={(event) => setDebugPayload(event.target.value)}
              placeholder="请输入 executeRule 所需的 JSON 参数"
            />
          </div>
          <div>
            <div className="mb-2 text-sm font-medium text-slate-900">执行结果</div>
            <Input.TextArea rows={14} value={debugResult} readOnly placeholder="点击“执行调试”后，这里会展示返回结果" />
          </div>
        </div>
      </Modal>
    </div>
  )
}
