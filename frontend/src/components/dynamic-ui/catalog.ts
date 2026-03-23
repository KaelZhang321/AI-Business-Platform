import { z } from 'zod'
import { defineCatalog } from '@json-render/core'
import { schema, type Spec } from '@json-render/react'

// ── Action types ──

const actionTypes = ['view_detail', 'refresh', 'export', 'open_link', 'trigger_task'] as const
export type UIActionType = (typeof actionTypes)[number]

// ── Component prop schemas (Zod) ──

export const cardPropsSchema = z.object({
  title: z.string().optional(),
  subtitle: z.string().optional(),
})

export const tablePropsSchema = z.object({
  title: z.string().optional(),
  columns: z.array(z.string()),
  data: z.array(z.array(z.unknown())),
})

export const metricPropsSchema = z.object({
  label: z.string(),
  value: z.union([z.string(), z.number()]),
  change: z.number().optional(),
  format: z.enum(['currency', 'percent', 'number']).optional(),
  trend: z.enum(['up', 'down', 'flat']).optional(),
})

const tagSchema = z.object({
  label: z.string(),
  color: z.string().optional(),
})

const listItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string().optional(),
  status: z.string().optional(),
  tags: z.array(tagSchema).optional(),
  assignee: z.string().optional(),
  dueDate: z.string().optional(),
  meta: z.record(z.string(), z.unknown()).optional(),
})

export const listPropsSchema = z.object({
  title: z.string().optional(),
  items: z.array(listItemSchema),
  emptyText: z.string().optional(),
})

const formFieldSchema = z.object({
  name: z.string(),
  label: z.string(),
  type: z.enum(['text', 'number', 'date', 'select']),
  required: z.boolean().default(false),
  placeholder: z.string().optional(),
  options: z
    .array(z.object({ label: z.string(), value: z.string() }))
    .optional(),
})

export const formPropsSchema = z.object({
  fields: z.array(formFieldSchema),
  submitLabel: z.string().optional(),
})

export const tagPropsSchema = z.object({
  label: z.string(),
  color: z.string().optional(),
})

export const chartPropsSchema = z.object({
  title: z.string().optional(),
  kind: z.enum(['bar', 'line', 'pie', 'scatter', 'radar']),
  option: z.record(z.string(), z.unknown()),
})

// ── json-render Catalog ──

export const catalog = defineCatalog(schema, {
  components: {
    Card: {
      props: cardPropsSchema,
      slots: ['default'],
      description: '容器卡片，可包含子组件',
    },
    Table: {
      props: tablePropsSchema,
      slots: [],
      description: '数据表格，columns 为列名数组，data 为二维数组',
    },
    Metric: {
      props: metricPropsSchema,
      slots: [],
      description: '指标数值展示',
    },
    List: {
      props: listPropsSchema,
      slots: [],
      description: '列表，展示任务/文档等条目',
    },
    Form: {
      props: formPropsSchema,
      slots: [],
      description: '表单，支持 text/number/date/select 字段',
    },
    Tag: {
      props: tagPropsSchema,
      slots: [],
      description: '标签',
    },
    Chart: {
      props: chartPropsSchema,
      slots: [],
      description: 'ECharts 图表，kind 指定类型，option 为 ECharts 配置',
    },
  },
  actions: {
    view_detail: {
      params: z.object({ id: z.string().optional() }),
      description: '查看详情',
    },
    refresh: {
      params: z.object({}),
      description: '刷新数据',
    },
    export: {
      params: z.object({ format: z.string().optional() }),
      description: '导出数据',
    },
    open_link: {
      params: z.object({ url: z.string() }),
      description: '打开外部链接',
    },
    trigger_task: {
      params: z.object({ taskId: z.string().optional() }),
      description: '触发任务',
    },
  },
})

// ── Legacy nested UISpec types (供 AI 网关老格式兼容) ──

export type UIAction = {
  type: UIActionType
  label?: string
  url?: string
  params?: Record<string, unknown>
}

export type ListItem = z.infer<typeof listItemSchema>

type UISpecType = 'Card' | 'Table' | 'Metric' | 'List' | 'Form' | 'Tag' | 'Chart'

export interface LegacyUISpec {
  type: UISpecType
  props: Record<string, unknown>
  children?: LegacyUISpec[]
  actions?: UIAction[]
}

/** json-render 的 Spec 格式 */
export type { Spec as UISpec }

// ── 格式转换：嵌套 → 扁平 ──

let keyCounter = 0
function nextKey() {
  return `e${++keyCounter}`
}

function flattenNode(
  node: LegacyUISpec,
  elements: Record<string, { type: string; props: Record<string, unknown>; children: string[] }>,
): string {
  const key = nextKey()
  const childKeys = (node.children ?? []).map((child) => flattenNode(child, elements))
  elements[key] = {
    type: node.type,
    props: node.props ?? {},
    children: childKeys,
  }
  return key
}

export function legacyToSpec(legacy: LegacyUISpec): Spec {
  keyCounter = 0
  const elements: Record<string, { type: string; props: Record<string, unknown>; children: string[] }> = {}
  const root = flattenNode(legacy, elements)
  return { root, elements } as Spec
}

// ── Spec 校验 ──

export function isJsonRenderSpec(spec: unknown): spec is Spec {
  return (
    typeof spec === 'object' &&
    spec !== null &&
    'root' in spec &&
    'elements' in spec
  )
}

export function isLegacySpec(spec: unknown): spec is LegacyUISpec {
  return (
    typeof spec === 'object' &&
    spec !== null &&
    'type' in spec &&
    typeof (spec as LegacyUISpec).type === 'string'
  )
}

export function normalizeSpec(spec: unknown): Spec | null {
  if (isJsonRenderSpec(spec)) return spec as Spec
  if (isLegacySpec(spec)) return legacyToSpec(spec)
  return null
}
