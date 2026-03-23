import { useMemo, type ReactNode } from 'react'
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Table,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
} from 'antd'
import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart, ScatterChart, RadarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent, DatasetComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { createRenderer, type ComponentRenderProps } from '@json-render/react'

import {
  catalog,
  normalizeSpec,
  type UISpec,
  type ListItem,
} from './catalog'

echarts.use([
  BarChart, LineChart, PieChart, ScatterChart, RadarChart,
  GridComponent, TooltipComponent, LegendComponent, TitleComponent, DatasetComponent,
  CanvasRenderer,
])

// ── json-render 组件注册 ──

const JsonRenderUI = createRenderer(catalog, {
  Card: ({ element, children }: ComponentRenderProps<{ title?: string; subtitle?: string }>) => (
    <Card
      title={
        <div className="flex flex-col">
          {element.props.title && <span className="font-medium">{element.props.title}</span>}
          {element.props.subtitle && <Typography.Text type="secondary">{element.props.subtitle}</Typography.Text>}
        </div>
      }
      className="mt-4"
    >
      {children}
    </Card>
  ),

  Table: ({ element }: ComponentRenderProps<{ title?: string; columns: string[]; data: unknown[][] }>) => {
    const { props } = element
    const columns = props.columns ?? []
    const data = props.data ?? []
    const dataSource = data.map((row, idx) => {
      const record: Record<string, unknown> = { key: `${idx}` }
      columns.forEach((col, ci) => { record[col] = row[ci] })
      return record
    })
    return (
      <Card size="small" title={props.title}>
        <Table
          columns={columns.map((col) => ({ title: col, dataIndex: col, key: col }))}
          dataSource={dataSource}
          pagination={false}
          size="small"
        />
      </Card>
    )
  },

  Metric: ({ element }: ComponentRenderProps<{
    label: string; value: string | number;
    format?: 'currency' | 'percent' | 'number'
  }>) => {
    const { props } = element
    const suffix = props.format === 'percent' ? '%' : props.format === 'currency' ? '元' : undefined
    return (
      <Statistic
        title={props.label}
        value={props.value}
        precision={props.format === 'percent' ? 2 : undefined}
        suffix={suffix}
      />
    )
  },

  List: ({ element }: ComponentRenderProps<{ title?: string; items: ListItem[]; emptyText?: string }>) => {
    const { props } = element
    const items = props.items ?? []
    if (!items.length) {
      return <Empty description={props.emptyText ?? '暂无数据'} />
    }
    return (
      <List
        itemLayout="horizontal"
        dataSource={items}
        header={props.title}
        renderItem={(item: ListItem) => (
          <List.Item key={item.id}>
            <List.Item.Meta
              title={
                <div className="flex flex-col sm:flex-row sm:items-center sm:gap-3">
                  <span>{item.title}</span>
                  <Space size="small">
                    {item.status && <Tag color={statusColor(item.status)}>{item.status}</Tag>}
                    {item.tags?.map((tag) => (
                      <Tag key={`${item.id}-${tag.label}`} color={tag.color}>{tag.label}</Tag>
                    ))}
                  </Space>
                </div>
              }
              description={
                <div className="flex flex-col gap-1">
                  {item.description && <Typography.Text type="secondary">{item.description}</Typography.Text>}
                  <Typography.Text type="secondary">
                    {item.assignee && `负责人：${item.assignee} `}
                    {item.dueDate && `截止：${item.dueDate}`}
                  </Typography.Text>
                </div>
              }
            />
          </List.Item>
        )}
      />
    )
  },

  Form: ({ element }: ComponentRenderProps<{
    fields: Array<{ name: string; label: string; type: string; required?: boolean; placeholder?: string; options?: Array<{ label: string; value: string }> }>
    submitLabel?: string
  }>) => (
    <Form layout="vertical">
      {element.props.fields?.map((field) => (
        <Form.Item key={field.name} label={field.label} required={field.required}>
          {renderFormField(field)}
        </Form.Item>
      ))}
      <Button type="primary">{element.props.submitLabel ?? '提交'}</Button>
    </Form>
  ),

  Tag: ({ element }: ComponentRenderProps<{ label: string; color?: string }>) => (
    <Tag color={element.props.color ?? 'blue'}>{element.props.label}</Tag>
  ),

  Chart: ({ element }: ComponentRenderProps<{
    title?: string; kind: string; option: Record<string, unknown>
  }>) => (
    <Card size="small" title={element.props.title}>
      <ReactEChartsCore
        echarts={echarts}
        option={element.props.option ?? {}}
        style={{ height: 320 }}
      />
    </Card>
  ),
})

// ── 主组件 ──

interface DynamicRendererProps {
  spec: UISpec | unknown | null | undefined
  loading?: boolean
}

export default function DynamicRenderer({ spec, loading = false }: DynamicRendererProps) {
  const normalizedSpec = useMemo(() => {
    if (!spec) return null
    return normalizeSpec(spec)
  }, [spec])

  if (!spec) return null

  if (loading) {
    return (
      <div className="py-8 flex justify-center">
        <Spin tip="AI 正在生成可视化" />
      </div>
    )
  }

  if (!normalizedSpec) {
    return (
      <Alert
        type="warning"
        showIcon
        message="动态UI解析失败"
        description="未提供可渲染的 UI Spec"
      />
    )
  }

  return (
    <div className="space-y-4">
      <JsonRenderUI spec={normalizedSpec} />
    </div>
  )
}

// ── 辅助函数 ──

function renderFormField(field: {
  type: string
  placeholder?: string
  options?: Array<{ label: string; value: string }>
}): ReactNode {
  switch (field.type) {
    case 'number':
      return <InputNumber className="w-full" placeholder={field.placeholder} />
    case 'date':
      return <DatePicker className="w-full" placeholder={field.placeholder} />
    case 'select':
      return (
        <Select placeholder={field.placeholder}>
          {field.options?.map((opt) => (
            <Select.Option key={opt.value} value={opt.value}>{opt.label}</Select.Option>
          ))}
        </Select>
      )
    default:
      return <Input placeholder={field.placeholder} />
  }
}

function statusColor(status: string) {
  if (status.includes('待')) return 'gold'
  if (status.includes('完成')) return 'green'
  if (status.includes('异常') || status.includes('失败')) return 'red'
  return 'blue'
}
