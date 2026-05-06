import { useEffect, useState, type ReactNode } from 'react'
import {
  Alert,
  Button,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Tabs,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'

type MaterialType =
  | 'PlannerCard'
  | 'PlannerBlankContainer'
  | 'PlannerMetricTiles'
  | 'PlannerInfoGrid'
  | 'PlannerForm'
  | 'PlannerInput'
  | 'PlannerSelect'
  | 'PlannerButton'
  | 'PlannerTable'
  | 'PlannerPagination'
  | 'PlannerNotice'

type ServiceTrigger = 'onMount' | 'onSubmit' | 'onClick' | 'onPageChange'

interface ServiceBinding {
  importPath: string
  methodName: string
  trigger: ServiceTrigger
  paramsExpression: string
  responsePath?: string
}

interface LowcodeNode {
  id: string
  type: MaterialType
  props: Record<string, unknown>
  children?: string[]
  bindings?: {
    service?: ServiceBinding
  }
}

interface LowcodeSchema {
  version: 1
  name: string
  rootId: string
  nodes: Record<string, LowcodeNode>
  updatedAt: string
}

interface MaterialField {
  key: string
  label: string
  kind: 'text' | 'number' | 'textarea' | 'select' | 'json'
  options?: Array<{ label: string; value: string }>
}

interface MaterialDefinition {
  type: MaterialType
  title: string
  description: string
  acceptsChildren: boolean
  defaultProps: Record<string, unknown>
  fields: MaterialField[]
}

const STORAGE_KEY = 'ai-platform-lowcode-builder:schema'
const MATERIAL_DRAG_DATA = 'application/x-ai-business-lowcode-material'

const materials: MaterialDefinition[] = [
  {
    type: 'PlannerCard',
    title: '业务卡片',
    description: '带标题、副标题和右侧标识的内容容器',
    acceptsChildren: true,
    defaultProps: {
      title: '客户画像',
      subtitle: '业务信息概览',
      headerRightText: '草稿',
    },
    fields: [
      { key: 'title', label: '标题', kind: 'text' },
      { key: 'subtitle', label: '副标题', kind: 'text' },
      { key: 'headerRightText', label: '右侧标签', kind: 'text' },
    ],
  },
  {
    type: 'PlannerBlankContainer',
    title: '空白容器',
    description: '承载其他组件的边框容器',
    acceptsChildren: true,
    defaultProps: { minHeight: 180 },
    fields: [{ key: 'minHeight', label: '最小高度', kind: 'number' }],
  },
  {
    type: 'PlannerMetricTiles',
    title: '指标卡片组',
    description: '参考 PlannerMetricTiles 的多指标展示',
    acceptsChildren: false,
    defaultProps: {
      minColumnWidth: 170,
      tiles: [
        { label: '可用余额', value: '2,043,360', desc: '当前可直接消费金额', tone: 'blue' },
        { label: '待跟进', value: '16', desc: '本周待处理事项', tone: 'amber' },
      ],
    },
    fields: [
      { key: 'minColumnWidth', label: '最小列宽', kind: 'number' },
      { key: 'tiles', label: '指标 JSON', kind: 'json' },
    ],
  },
  {
    type: 'PlannerInfoGrid',
    title: '信息网格',
    description: 'label/value 信息展示',
    acceptsChildren: false,
    defaultProps: {
      minColumnWidth: 160,
      items: [
        { label: '客户姓名', value: '张三' },
        { label: '联系电话', value: '13800138000' },
        { label: '最近体检日期', value: '2026-04-10' },
      ],
    },
    fields: [
      { key: 'minColumnWidth', label: '最小列宽', kind: 'number' },
      { key: 'items', label: '信息项 JSON', kind: 'json' },
    ],
  },
  {
    type: 'PlannerForm',
    title: '查询表单',
    description: '容纳输入项和按钮的业务表单',
    acceptsChildren: true,
    defaultProps: { formCode: 'customerSearch' },
    fields: [{ key: 'formCode', label: '表单编码', kind: 'text' }],
  },
  {
    type: 'PlannerInput',
    title: '输入框',
    description: '表单输入项',
    acceptsChildren: false,
    defaultProps: { label: '客户姓名', placeholder: '请输入', required: false },
    fields: [
      { key: 'label', label: '标签', kind: 'text' },
      { key: 'placeholder', label: '占位文案', kind: 'text' },
      {
        key: 'required',
        label: '是否必填',
        kind: 'select',
        options: [
          { label: '否', value: 'false' },
          { label: '是', value: 'true' },
        ],
      },
    ],
  },
  {
    type: 'PlannerSelect',
    title: '字典下拉',
    description: '从项目 service/request 加载选项',
    acceptsChildren: false,
    defaultProps: { label: '客户类型', dictCode: 'customer_type', placeholder: '请选择' },
    fields: [
      { key: 'label', label: '标签', kind: 'text' },
      { key: 'dictCode', label: '字典编码', kind: 'text' },
      { key: 'placeholder', label: '占位文案', kind: 'text' },
    ],
  },
  {
    type: 'PlannerButton',
    title: '按钮',
    description: '触发查询、提交或自定义 service 调用',
    acceptsChildren: false,
    defaultProps: { label: '查询', variant: 'primary' },
    fields: [
      { key: 'label', label: '按钮文案', kind: 'text' },
      {
        key: 'variant',
        label: '按钮类型',
        kind: 'select',
        options: [
          { label: '主按钮', value: 'primary' },
          { label: '次按钮', value: 'secondary' },
        ],
      },
    ],
  },
  {
    type: 'PlannerTable',
    title: '业务表格',
    description: '展示静态数据或绑定 service 响应',
    acceptsChildren: false,
    defaultProps: {
      title: '本周跟进任务',
      columns: [
        { key: 'task', title: '任务', dataIndex: 'task' },
        { key: 'owner', title: '负责人', dataIndex: 'owner' },
        { key: 'status', title: '状态', dataIndex: 'status' },
      ],
      rows: [
        { id: 't1', task: '睡眠问卷回访', owner: '李健管', status: '进行中' },
        { id: 't2', task: '饮食计划确认', owner: '王顾问', status: '待开始' },
      ],
    },
    fields: [
      { key: 'title', label: '标题', kind: 'text' },
      { key: 'columns', label: '列配置 JSON', kind: 'json' },
      { key: 'rows', label: '静态数据 JSON', kind: 'json' },
    ],
  },
  {
    type: 'PlannerPagination',
    title: '分页器',
    description: '表格分页状态展示和翻页触发',
    acceptsChildren: false,
    defaultProps: { total: 42, currentPage: 1, pageSize: 10 },
    fields: [
      { key: 'total', label: '总数', kind: 'number' },
      { key: 'currentPage', label: '当前页', kind: 'number' },
      { key: 'pageSize', label: '每页条数', kind: 'number' },
    ],
  },
  {
    type: 'PlannerNotice',
    title: '提示',
    description: '业务状态提示',
    acceptsChildren: false,
    defaultProps: { text: '建议优先从作息管理与压力干预切入，2 周后复评。', tone: 'info' },
    fields: [
      { key: 'text', label: '提示内容', kind: 'textarea' },
      {
        key: 'tone',
        label: '语义',
        kind: 'select',
        options: [
          { label: '信息', value: 'info' },
          { label: '成功', value: 'success' },
          { label: '警告', value: 'warning' },
        ],
      },
    ],
  },
]

const materialMap = Object.fromEntries(materials.map((material) => [material.type, material])) as Record<
  MaterialType,
  MaterialDefinition
>

export function LowCodeBuilderTab() {
  const [messageApi, contextHolder] = message.useMessage()
  const [schema, setSchema] = useState<LowcodeSchema>(() => loadSavedSchema() ?? createInitialSchema())
  const [selectedId, setSelectedId] = useState(schema.rootId)
  const [sourceText, setSourceText] = useState('')

  useEffect(() => {
    setSourceText(generateReactSource(schema))
  }, [schema])

  const selectedNode = schema.nodes[selectedId] ?? schema.nodes[schema.rootId]
  const parentId = getSelectableParentId(schema, selectedId)
  const selectedMaterial = selectedNode ? materialMap[selectedNode.type] : undefined

  function updateSchema(nextSchema: LowcodeSchema) {
    setSchema({ ...nextSchema, updatedAt: new Date().toISOString() })
  }

  function addMaterial(type: MaterialType, targetParentId = parentId) {
    const parent = schema.nodes[targetParentId]
    if (!parent || !materialMap[parent.type].acceptsChildren) {
      messageApi.warning('请选择可承载子组件的容器')
      return
    }
    const id = `${type}-${crypto.randomUUID().slice(0, 8)}`
    const material = materialMap[type]
    updateSchema({
      ...schema,
      nodes: {
        ...schema.nodes,
        [parent.id]: {
          ...parent,
          children: [...(parent.children ?? []), id],
        },
        [id]: {
          id,
          type,
          props: structuredClone(material.defaultProps),
          children: material.acceptsChildren ? [] : undefined,
        },
      },
    })
    setSelectedId(id)
  }

  function handleMaterialDrop(type: MaterialType, targetParentId: string) {
    addMaterial(type, targetParentId)
    messageApi.success(`已添加 ${materialMap[type].title}`)
  }

  function updateProp(key: string, value: unknown) {
    if (!selectedNode) return
    updateSchema({
      ...schema,
      nodes: {
        ...schema.nodes,
        [selectedNode.id]: {
          ...selectedNode,
          props: {
            ...selectedNode.props,
            [key]: value,
          },
        },
      },
    })
  }

  function updateBinding(patch: Partial<ServiceBinding>) {
    if (!selectedNode) return
    const current = selectedNode.bindings?.service ?? {
      importPath: '../services/api',
      methodName: 'apiClient.get',
      trigger: 'onClick' as ServiceTrigger,
      paramsExpression: "'/api/v1/demo'",
      responsePath: 'data.data',
    }
    updateSchema({
      ...schema,
      nodes: {
        ...schema.nodes,
        [selectedNode.id]: {
          ...selectedNode,
          bindings: {
            ...selectedNode.bindings,
            service: {
              ...current,
              ...patch,
            },
          },
        },
      },
    })
  }

  function removeBinding() {
    if (!selectedNode) return
    updateSchema({
      ...schema,
      nodes: {
        ...schema.nodes,
        [selectedNode.id]: {
          ...selectedNode,
          bindings: undefined,
        },
      },
    })
  }

  function removeNode() {
    if (!selectedNode || selectedNode.id === schema.rootId) return
    const ids = collectDescendants(schema, selectedNode.id)
    const nodes = { ...schema.nodes }
    ids.forEach((id) => delete nodes[id])
    Object.values(nodes).forEach((node: LowcodeNode) => {
      if (node.children?.includes(selectedNode.id)) {
        nodes[node.id] = {
          ...node,
          children: node.children.filter((childId) => childId !== selectedNode.id),
        }
      }
    })
    updateSchema({ ...schema, nodes })
    setSelectedId(schema.rootId)
  }

  function saveCurrentSchema() {
    const nextSchema = { ...schema, updatedAt: new Date().toISOString() }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextSchema, null, 2))
    setSchema(nextSchema)
    messageApi.success('schema 已保存，可再次打开继续编辑')
  }

  function importSchema(file?: File) {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const nextSchema = JSON.parse(String(reader.result)) as LowcodeSchema
        setSchema(nextSchema)
        setSelectedId(nextSchema.rootId)
        messageApi.success('schema 已导入')
      } catch {
        messageApi.error('schema JSON 解析失败')
      }
    }
    reader.readAsText(file)
  }

  return (
    <div className="space-y-6">
      {contextHolder}
      <Alert
        type="info"
        showIcon
        message="低代码搭建器 MVP"
        description="schema 是唯一编辑源；当前 Tab 支持拖拽物料到预览容器、真实项目环境预览、保存/重新打开 schema，并生成可接入当前 React 项目的源码骨架。"
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={5}>
          <section className="h-full rounded-[24px] border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
              <div className="font-semibold text-slate-900">物料</div>
              <div className="mt-1 text-xs text-slate-500">拖到预览容器，或点击添加到当前选中容器</div>
            </div>
            <div className="p-5">
              <div className="grid gap-3">
                {materials.map((material) => (
                  <button
                    key={material.type}
                    type="button"
                    draggable
                    className="cursor-grab rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-sky-300 hover:bg-sky-50 active:cursor-grabbing"
                    onClick={() => addMaterial(material.type)}
                    onDragStart={(event) => {
                      event.dataTransfer.effectAllowed = 'copy'
                      event.dataTransfer.setData(MATERIAL_DRAG_DATA, material.type)
                    }}
                  >
                    <div className="font-semibold text-slate-900">{material.title}</div>
                    <div className="mt-1 text-xs text-slate-500">{material.description}</div>
                  </button>
                ))}
              </div>
            </div>
          </section>
        </Col>

        <Col xs={24} xl={13}>
          <section className="rounded-[24px] border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="font-semibold text-slate-900">实时预览</span>
                <Space wrap>
                  <Button onClick={saveCurrentSchema}>保存 schema</Button>
                  <Button onClick={() => downloadJson(schema, `${safeFileName(schema.name)}.schema.json`)}>
                    导出 schema
                  </Button>
                  <Button type="primary" onClick={() => downloadText(sourceText, `${safeFileName(schema.name)}.tsx`)}>
                    导出源码
                  </Button>
                  <label className="inline-flex cursor-pointer items-center rounded-lg border border-slate-200 px-3 py-1.5 text-sm">
                    导入 schema
                    <input
                      type="file"
                      accept="application/json"
                      className="hidden"
                      onChange={(event) => importSchema(event.target.files?.[0])}
                    />
                  </label>
                </Space>
              </div>
            </div>
            <div className="p-5">
              <div className="rounded-[28px] border border-dashed border-slate-300 bg-slate-50/70 p-5">
                <PreviewNode
                  schema={schema}
                  nodeId={schema.rootId}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  onDropMaterial={handleMaterialDrop}
                />
              </div>
            </div>
          </section>
        </Col>

        <Col xs={24} xl={6}>
          <section className="h-full rounded-[24px] border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4 font-semibold text-slate-900">属性与绑定</div>
            <div className="p-5">
              {!selectedNode || !selectedMaterial ? (
                <Typography.Text type="secondary">请选择节点</Typography.Text>
              ) : (
                <div className="space-y-5">
                  <div>
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <Typography.Title level={5} style={{ margin: 0 }}>
                          {selectedMaterial.title}
                        </Typography.Title>
                        <Typography.Text type="secondary">{selectedNode.id}</Typography.Text>
                      </div>
                      <Button danger disabled={selectedNode.id === schema.rootId} onClick={removeNode}>
                        删除
                      </Button>
                    </div>
                  </div>

                  <Form layout="vertical">
                    {selectedMaterial.fields.map((field) => (
                      <div key={field.key}>
                        <Form.Item label={field.label}>
                          <FieldInput
                            field={field}
                            value={selectedNode.props[field.key]}
                            onChange={(value) => updateProp(field.key, value)}
                          />
                        </Form.Item>
                      </div>
                    ))}
                  </Form>

                  <Divider />
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <Typography.Title level={5} style={{ margin: 0 }}>
                          Service 绑定
                        </Typography.Title>
                        <Typography.Text type="secondary">生成源码时转成项目 service 调用</Typography.Text>
                      </div>
                      {selectedNode.bindings?.service ? (
                        <Button onClick={removeBinding}>移除</Button>
                      ) : (
                        <Button onClick={() => updateBinding({})}>添加</Button>
                      )}
                    </div>

                    {selectedNode.bindings?.service ? (
                      <ServiceBindingForm binding={selectedNode.bindings.service} onChange={updateBinding} />
                    ) : (
                      <Typography.Text type="secondary">未绑定 service，组件会以静态 props 生成。</Typography.Text>
                    )}
                  </div>
                </div>
              )}
            </div>
          </section>
        </Col>
      </Row>

      <section className="rounded-[24px] border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-4 font-semibold text-slate-900">生成的 React 源码</div>
        <div className="p-5">
          <Tabs
            items={[
              {
                key: 'tsx',
                label: 'TSX',
                children: (
                  <pre className="max-h-[520px] overflow-auto rounded-2xl bg-slate-950 p-5 text-xs leading-6 text-sky-50">
                    {sourceText}
                  </pre>
                ),
              },
              {
                key: 'schema',
                label: 'Schema',
                children: (
                  <pre className="max-h-[520px] overflow-auto rounded-2xl bg-slate-950 p-5 text-xs leading-6 text-sky-50">
                    {JSON.stringify(schema, null, 2)}
                  </pre>
                ),
              },
            ]}
          />
        </div>
      </section>
    </div>
  )
}

function FieldInput({ field, value, onChange }: { field: MaterialField; value: unknown; onChange: (value: unknown) => void }) {
  if (field.kind === 'number') {
    return <InputNumber className="w-full" value={Number(value)} onChange={(nextValue) => onChange(nextValue ?? 0)} />
  }
  if (field.kind === 'textarea') {
    return <Input.TextArea rows={4} value={String(value ?? '')} onChange={(event) => onChange(event.target.value)} />
  }
  if (field.kind === 'select') {
    return (
      <Select
        value={String(value ?? '')}
        options={field.options}
        onChange={(nextValue) => onChange(nextValue === 'true' ? true : nextValue === 'false' ? false : nextValue)}
      />
    )
  }
  if (field.kind === 'json') {
    return (
      <Input.TextArea
        rows={7}
        value={typeof value === 'string' ? value : JSON.stringify(value ?? null, null, 2)}
        onChange={(event) => {
          try {
            onChange(JSON.parse(event.target.value))
          } catch {
            onChange(event.target.value)
          }
        }}
      />
    )
  }
  return <Input value={String(value ?? '')} onChange={(event) => onChange(event.target.value)} />
}

function ServiceBindingForm({ binding, onChange }: { binding: ServiceBinding; onChange: (patch: Partial<ServiceBinding>) => void }) {
  return (
    <Form layout="vertical">
      <Form.Item label="import 路径">
        <Input value={binding.importPath} onChange={(event) => onChange({ importPath: event.target.value })} />
      </Form.Item>
      <Form.Item label="方法名">
        <Input value={binding.methodName} onChange={(event) => onChange({ methodName: event.target.value })} />
      </Form.Item>
      <Form.Item label="触发时机">
        <Select
          value={binding.trigger}
          options={[
            { label: '组件加载', value: 'onMount' },
            { label: '表单提交', value: 'onSubmit' },
            { label: '点击', value: 'onClick' },
            { label: '分页变化', value: 'onPageChange' },
          ]}
          onChange={(trigger) => onChange({ trigger })}
        />
      </Form.Item>
      <Form.Item label="参数表达式">
        <Input.TextArea rows={3} value={binding.paramsExpression} onChange={(event) => onChange({ paramsExpression: event.target.value })} />
      </Form.Item>
      <Form.Item label="响应路径">
        <Input value={binding.responsePath} onChange={(event) => onChange({ responsePath: event.target.value })} />
      </Form.Item>
    </Form>
  )
}

function PreviewNode({
  schema,
  nodeId,
  selectedId,
  onSelect,
  onDropMaterial,
}: {
  schema: LowcodeSchema
  nodeId: string
  selectedId: string
  onSelect: (nodeId: string) => void
  onDropMaterial: (type: MaterialType, targetParentId: string) => void
}) {
  const node = schema.nodes[nodeId]
  if (!node) return null
  const acceptsChildren = materialMap[node.type].acceptsChildren
  const children = node.children?.map((childId) => (
    <div key={childId}>
      <PreviewNode
        schema={schema}
        nodeId={childId}
        selectedId={selectedId}
        onSelect={onSelect}
        onDropMaterial={onDropMaterial}
      />
    </div>
  ))

  return (
    <div
      className={`rounded-[22px] border transition ${
        selectedId === node.id ? 'border-sky-400 shadow-[0_0_0_3px_rgba(14,165,233,0.15)]' : 'border-transparent hover:border-sky-200'
      }`}
      onClick={(event) => {
        event.stopPropagation()
        onSelect(node.id)
      }}
      onDragOver={(event) => {
        if (!acceptsChildren || !event.dataTransfer.types.includes(MATERIAL_DRAG_DATA)) return
        event.preventDefault()
        event.stopPropagation()
        event.dataTransfer.dropEffect = 'copy'
      }}
      onDrop={(event) => {
        if (!acceptsChildren) return
        const type = event.dataTransfer.getData(MATERIAL_DRAG_DATA) as MaterialType
        if (!type || !materialMap[type]) return
        event.preventDefault()
        event.stopPropagation()
        onSelect(node.id)
        onDropMaterial(type, node.id)
      }}
    >
      <PreviewNodeBody node={node}>{children}</PreviewNodeBody>
    </div>
  )
}

function PreviewNodeBody({ node, children }: { node: LowcodeNode; children?: ReactNode }) {
  switch (node.type) {
    case 'PlannerCard':
      return (
        <section className="mb-5 rounded-[28px] border border-slate-200/80 bg-gradient-to-b from-white to-slate-50/60 p-5 shadow-sm">
          <header className="mb-4 flex items-start justify-between gap-4 border-b border-slate-100 pb-3">
            <div className="flex items-start gap-2">
              <span className="mt-1 h-5 w-1.5 rounded-full bg-blue-500" />
              <div>
                <h3 className="m-0 text-lg font-bold text-slate-800">{asText(node.props.title)}</h3>
                {node.props.subtitle ? <p className="mt-1 text-xs text-slate-500">{asText(node.props.subtitle)}</p> : null}
              </div>
            </div>
            {node.props.headerRightText ? (
              <Tag color="blue" className="rounded-full">
                {asText(node.props.headerRightText)}
              </Tag>
            ) : null}
          </header>
          <div className="space-y-3">{children}</div>
        </section>
      )
    case 'PlannerBlankContainer':
      return (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 p-3" style={{ minHeight: asNumber(node.props.minHeight) }}>
          {children}
        </div>
      )
    case 'PlannerMetricTiles':
      return (
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${asNumber(node.props.minColumnWidth, 170)}px, 1fr))` }}>
          {asArray(node.props.tiles).map((tile, index) => (
            <div key={`${asText(tile.label)}-${index}`} className={`rounded-2xl border bg-gradient-to-br p-4 ${toneClass(asText(tile.tone, 'blue'))}`}>
              <div className="text-xs text-slate-500">{asText(tile.label)}</div>
              <div className="mt-2 text-2xl font-bold text-slate-900">{asText(tile.value, '-')}</div>
              {tile.desc ? <div className="mt-1 text-xs text-slate-500">{asText(tile.desc)}</div> : null}
            </div>
          ))}
        </div>
      )
    case 'PlannerInfoGrid':
      return (
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${asNumber(node.props.minColumnWidth, 160)}px, 1fr))` }}>
          {asArray(node.props.items).map((item, index) => (
            <div key={`${asText(item.label)}-${index}`} className="space-y-1">
              <div className="text-sm text-slate-500">{asText(item.label)}</div>
              <div className="truncate text-sm font-semibold text-slate-900">{asText(item.value, '-')}</div>
            </div>
          ))}
        </div>
      )
    case 'PlannerForm':
      return <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-3 md:grid-cols-3">{children}</div>
    case 'PlannerInput':
      return (
        <label className="block rounded-2xl border border-slate-200 bg-white px-3 py-2">
          <span className="text-[11px] font-semibold text-slate-500">{asText(node.props.label)}</span>
          <Input bordered={false} placeholder={asText(node.props.placeholder)} readOnly />
        </label>
      )
    case 'PlannerSelect':
      return (
        <label className="block rounded-2xl border border-slate-200 bg-white px-3 py-2">
          <span className="text-[11px] font-semibold text-slate-500">{asText(node.props.label)}</span>
          <Select
            className="w-full"
            bordered={false}
            placeholder={asText(node.props.placeholder) || '请选择'}
            options={[{ label: `${asText(node.props.dictCode)} / 示例`, value: 'sample' }]}
          />
          {node.bindings?.service ? <Tag color="processing">service: {node.bindings.service.methodName}</Tag> : null}
        </label>
      )
    case 'PlannerButton':
      return (
        <Button type={node.props.variant === 'secondary' ? 'default' : 'primary'} className="rounded-xl">
          {asText(node.props.label)}
        </Button>
      )
    case 'PlannerTable':
      return <PreviewTable node={node} />
    case 'PlannerPagination':
      return (
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>
            第 {asNumber(node.props.currentPage, 1)} 页 / 每页 {asNumber(node.props.pageSize, 10)} 条 / 共 {asNumber(node.props.total)} 条
          </span>
          <Space>
            <Button>上一页</Button>
            <Button>下一页</Button>
          </Space>
        </div>
      )
    case 'PlannerNotice':
      return <Alert type={node.props.tone === 'warning' ? 'warning' : node.props.tone === 'success' ? 'success' : 'info'} message={asText(node.props.text)} showIcon />
    default:
      return null
  }
}

function PreviewTable({ node }: { node: LowcodeNode }) {
  const columns = asArray(node.props.columns).map((column) => ({
    title: asText(column.title),
    dataIndex: asText(column.dataIndex),
    key: asText(column.key),
  }))
  return <Table size="small" rowKey={(record) => String(record.id ?? JSON.stringify(record))} columns={columns} dataSource={asArray(node.props.rows)} pagination={false} />
}

function createInitialSchema(): LowcodeSchema {
  return {
    version: 1,
    name: '客户画像业务页',
    rootId: 'root',
    updatedAt: new Date().toISOString(),
    nodes: {
      root: {
        id: 'root',
        type: 'PlannerBlankContainer',
        props: { minHeight: 520 },
        children: ['card-1'],
      },
      'card-1': {
        id: 'card-1',
        type: 'PlannerCard',
        props: {
          title: '客户画像结构化展示',
          subtitle: '通用原子 + 少量复合组件示例',
          headerRightText: 'AI 草案',
        },
        children: ['metrics-1', 'form-1', 'table-1', 'pagination-1', 'notice-1'],
      },
      'metrics-1': {
        id: 'metrics-1',
        type: 'PlannerMetricTiles',
        props: materialMap.PlannerMetricTiles.defaultProps,
      },
      'form-1': {
        id: 'form-1',
        type: 'PlannerForm',
        props: materialMap.PlannerForm.defaultProps,
        children: ['input-1', 'select-1', 'button-1'],
      },
      'input-1': {
        id: 'input-1',
        type: 'PlannerInput',
        props: materialMap.PlannerInput.defaultProps,
      },
      'select-1': {
        id: 'select-1',
        type: 'PlannerSelect',
        props: materialMap.PlannerSelect.defaultProps,
        bindings: {
          service: {
            importPath: '../services/api',
            methodName: 'apiClient.get',
            trigger: 'onMount',
            paramsExpression: '`/api/v1/system/dict/data/type/${dictCode}`',
            responsePath: 'data.data',
          },
        },
      },
      'button-1': {
        id: 'button-1',
        type: 'PlannerButton',
        props: materialMap.PlannerButton.defaultProps,
        bindings: {
          service: {
            importPath: '../services/api/aiReportApi',
            methodName: 'aiReportApi.getcustomersListApi',
            trigger: 'onClick',
            paramsExpression: '{ pageNo: 1, pageSize: 10 }',
            responsePath: 'data',
          },
        },
      },
      'table-1': {
        id: 'table-1',
        type: 'PlannerTable',
        props: materialMap.PlannerTable.defaultProps,
      },
      'pagination-1': {
        id: 'pagination-1',
        type: 'PlannerPagination',
        props: materialMap.PlannerPagination.defaultProps,
      },
      'notice-1': {
        id: 'notice-1',
        type: 'PlannerNotice',
        props: materialMap.PlannerNotice.defaultProps,
      },
    },
  }
}

function loadSavedSchema(): LowcodeSchema | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as LowcodeSchema
  } catch {
    return null
  }
}

function getSelectableParentId(schema: LowcodeSchema, selectedId: string) {
  const selected = schema.nodes[selectedId]
  if (selected && materialMap[selected.type].acceptsChildren) return selected.id
  const parent = Object.values(schema.nodes).find((node) => node.children?.includes(selectedId))
  return parent?.id ?? schema.rootId
}

function collectDescendants(schema: LowcodeSchema, nodeId: string): string[] {
  const node = schema.nodes[nodeId]
  if (!node) return []
  return [nodeId, ...(node.children ?? []).flatMap((childId) => collectDescendants(schema, childId))]
}

function generateReactSource(schema: LowcodeSchema) {
  const serviceImports = collectServiceImports(schema)
  const stateLines = collectStateLines(schema)
  const effectLines = collectEffectLines(schema)
  const handlerLines = collectHandlerLines(schema)
  const markup = renderNodeSource(schema, schema.rootId, 3)

  return `import { useEffect, useState } from 'react'
${serviceImports.join('\n')}

export default function ${toComponentName(schema.name)}() {
${stateLines.join('\n')}
${effectLines.join('\n')}
${handlerLines.join('\n')}

  return (
${markup}
  )
}
`
}

function collectServiceImports(schema: LowcodeSchema) {
  const imports = new Map<string, Set<string>>()
  Object.values(schema.nodes).forEach((node) => {
    const binding = node.bindings?.service
    if (!binding) return
    const importName = binding.methodName.split('.')[0]
    const names = imports.get(binding.importPath) ?? new Set<string>()
    names.add(importName)
    imports.set(binding.importPath, names)
  })
  return Array.from(imports.entries()).map(([path, names]) => `import { ${Array.from(names).sort().join(', ')} } from '${path}'`)
}

function collectStateLines(schema: LowcodeSchema) {
  return Object.values(schema.nodes).flatMap((node) => {
    if (node.type === 'PlannerTable') {
      return [`  const [${toVariableName(node.id)}Rows, set${toPascal(node.id)}Rows] = useState(${JSON.stringify(node.props.rows ?? [], null, 2)})`]
    }
    if (node.type === 'PlannerSelect') {
      return [`  const [${toVariableName(node.id)}Options, set${toPascal(node.id)}Options] = useState<Array<{ label: string; value: string }>>([])`]
    }
    return []
  })
}

function collectEffectLines(schema: LowcodeSchema) {
  return Object.values(schema.nodes)
    .filter((node) => node.bindings?.service?.trigger === 'onMount')
    .map((node) => {
      const binding = node.bindings!.service!
      const setter = node.type === 'PlannerSelect' ? `set${toPascal(node.id)}Options` : node.type === 'PlannerTable' ? `set${toPascal(node.id)}Rows` : null
      return `
  useEffect(() => {
    let alive = true
    ${binding.methodName}(${binding.paramsExpression})
      .then((result) => {
        if (!alive) return
        ${setter ? `${setter}(readPath(result, '${binding.responsePath ?? 'data'}') ?? [])` : 'console.info(result)'}
      })
      .catch((error) => console.error('[${node.id}] service binding failed:', error))
    return () => {
      alive = false
    }
  }, [])`
    })
}

function collectHandlerLines(schema: LowcodeSchema) {
  const handlers = Object.values(schema.nodes).filter((node) => {
    const trigger = node.bindings?.service?.trigger
    return trigger === 'onClick' || trigger === 'onSubmit' || trigger === 'onPageChange'
  })
  return [
    `
  function readPath(source: unknown, path: string) {
    return path.split('.').reduce<unknown>((current, key) => {
      if (!current || typeof current !== 'object') return undefined
      return (current as Record<string, unknown>)[key]
    }, source)
  }`,
    ...handlers.map((node) => {
      const binding = node.bindings!.service!
      return `
  async function handle${toPascal(node.id)}() {
    const result = await ${binding.methodName}(${binding.paramsExpression})
    console.info('[${node.id}] service result:', result)
  }`
    }),
  ]
}

function renderNodeSource(schema: LowcodeSchema, nodeId: string, depth: number): string {
  const node = schema.nodes[nodeId]
  if (!node) return ''
  const indent = '  '.repeat(depth)
  const childIndent = '  '.repeat(depth + 1)
  const children = node.children?.map((childId) => renderNodeSource(schema, childId, depth + 1)).join('\n') ?? ''
  switch (node.type) {
    case 'PlannerCard':
      return `${indent}<section className="planner-card">
${childIndent}<header className="planner-card-header">
${childIndent}  <h2>${jsxText(node.props.title)}</h2>
${childIndent}  <span>${jsxText(node.props.headerRightText)}</span>
${childIndent}</header>
${children}
${indent}</section>`
    case 'PlannerBlankContainer':
      return `${indent}<div className="planner-blank" style={{ minHeight: ${asNumber(node.props.minHeight)} }}>
${children}
${indent}</div>`
    case 'PlannerMetricTiles':
      return `${indent}<div className="metric-grid">
${asArray(node.props.tiles).map((tile) => `${childIndent}<article className="metric-tile"><span>${jsxText(tile.label)}</span><strong>${jsxText(tile.value)}</strong><small>${jsxText(tile.desc)}</small></article>`).join('\n')}
${indent}</div>`
    case 'PlannerInfoGrid':
      return `${indent}<dl className="info-grid">
${asArray(node.props.items).map((item) => `${childIndent}<div><dt>${jsxText(item.label)}</dt><dd>${jsxText(item.value)}</dd></div>`).join('\n')}
${indent}</dl>`
    case 'PlannerForm':
      return `${indent}<form className="planner-form">
${children}
${indent}</form>`
    case 'PlannerInput':
      return `${indent}<label><span>${jsxText(node.props.label)}</span><input placeholder="${escapeAttribute(asText(node.props.placeholder))}" /></label>`
    case 'PlannerSelect':
      return `${indent}<label><span>${jsxText(node.props.label)}</span><select>{${toVariableName(node.id)}Options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>`
    case 'PlannerButton':
      return `${indent}<button type="button"${node.bindings?.service ? ` onClick={handle${toPascal(node.id)}}` : ''}>${jsxText(node.props.label)}</button>`
    case 'PlannerTable': {
      const rowsVar = `${toVariableName(node.id)}Rows`
      const columns = asArray(node.props.columns)
      return `${indent}<table>
${childIndent}<thead><tr>${columns.map((column) => `<th>${jsxText(column.title)}</th>`).join('')}</tr></thead>
${childIndent}<tbody>{${rowsVar}.map((row, index) => <tr key={String(row.id ?? index)}>${columns.map((column) => `<td>{String(row['${escapeAttribute(asText(column.dataIndex))}'] ?? '-')}</td>`).join('')}</tr>)}</tbody>
${indent}</table>`
    }
    case 'PlannerPagination':
      return `${indent}<div>共 ${asNumber(node.props.total)} 条</div>`
    case 'PlannerNotice':
      return `${indent}<div>${jsxText(node.props.text)}</div>`
    default:
      return ''
  }
}

function downloadJson(value: unknown, fileName: string) {
  downloadText(JSON.stringify(value, null, 2), fileName, 'application/json;charset=utf-8')
}

function downloadText(text: string, fileName: string, type = 'text/plain;charset=utf-8') {
  const blob = new Blob([text], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function asArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === 'object') : []
}

function asText(value: unknown, fallback = '') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function asNumber(value: unknown, fallback = 0) {
  const nextValue = Number(value)
  return Number.isFinite(nextValue) ? nextValue : fallback
}

function toneClass(tone: string) {
  switch (tone) {
    case 'emerald':
      return 'border-emerald-100 from-emerald-50 to-emerald-100/60 text-emerald-700'
    case 'amber':
      return 'border-amber-100 from-amber-50 to-amber-100/60 text-amber-700'
    case 'rose':
      return 'border-rose-100 from-rose-50 to-rose-100/60 text-rose-700'
    default:
      return 'border-blue-100 from-blue-50 to-blue-100/60 text-blue-700'
  }
}

function toComponentName(name: string) {
  const ascii = name.replace(/[^\w ]/g, '').trim()
  return `${toPascal(ascii || 'GeneratedPlanner')}Page`
}

function toPascal(value: string) {
  return value
    .split(/[^a-zA-Z0-9]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('')
}

function toVariableName(value: string) {
  const pascal = toPascal(value)
  return pascal.charAt(0).toLowerCase() + pascal.slice(1)
}

function safeFileName(value: string) {
  return value.trim().replace(/[^\w\u4e00-\u9fa5-]+/g, '-').replace(/-+/g, '-') || 'lowcode-page'
}

function jsxText(value: unknown) {
  return asText(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
}

function escapeAttribute(value: string) {
  return value.replaceAll('"', '&quot;')
}
