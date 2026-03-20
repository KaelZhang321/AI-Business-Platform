import { useMemo, type ReactElement } from 'react'
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

import { validateUISpec, type UISpec, type UIAction, type ListItem } from './catalog'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  RadarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
  CanvasRenderer,
])

interface DynamicRendererProps {
  spec: UISpec | null | undefined
  loading?: boolean
}

export default function DynamicRenderer({ spec, loading = false }: DynamicRendererProps) {
  const validation = useMemo(() => {
    if (!spec) return null
    return validateUISpec(spec)
  }, [spec])

  if (!spec) return null

  if (loading) {
    return (
      <div className="py-8 flex justify-center">
        <Spin tip="AI 正在生成可视化" />
      </div>
    )
  }

  if (!validation?.success) {
    return (
      <Alert
        type="warning"
        showIcon
        message="动态UI解析失败"
        description={validation?.errors?.join('\n') ?? '未提供可渲染的 UI Spec'}
      />
    )
  }

  return <div className="space-y-4">{renderNode(validation.spec)}</div>
}

function renderNode(node: UISpec): ReactElement {
  const { type, props = {}, children } = node

  switch (type) {
    case 'Card':
      return (
        <Card
          title={
            <div className="flex flex-col">
              {props.title && <span className="font-medium">{props.title}</span>}
              {props.subtitle && <Typography.Text type="secondary">{props.subtitle}</Typography.Text>}
            </div>
          }
          className="mt-4"
          extra={renderActions(props.actions as UIAction[] | undefined)}
        >
          {children?.map((child, i) => (
            <div key={`${child.type}-${i}`} className={i > 0 ? 'mt-4' : ''}>
              {renderNode(child)}
            </div>
          ))}
        </Card>
      )

    case 'Table': {
      const columns = (props.columns as string[]) ?? []
      const data = (props.data as unknown[][]) ?? []
      const dataSource = data.map((row, index) => {
        const record: Record<string, unknown> = { key: `${index}` }
        columns.forEach((col, colIndex) => {
          record[col] = row[colIndex]
        })
        return record
      })
      return (
        <Card size="small" title={props.title as string} extra={renderActions(props.actions as UIAction[] | undefined)}>
          <Table
            columns={columns.map((col) => ({ title: col, dataIndex: col, key: col }))}
            dataSource={dataSource}
            pagination={false}
            size="small"
          />
        </Card>
      )
    }

    case 'Metric': {
      const suffix =
        props.format === 'percent' ? '%' : props.format === 'currency' ? '元' : undefined
      return (
        <Statistic
          title={props.label as string}
          value={props.value as string | number}
          precision={props.format === 'percent' ? 2 : undefined}
          suffix={suffix}
        />
      )
    }

    case 'List': {
      const items = (props.items as ListItem[]) ?? []
      if (!items.length) {
        return <Empty description={props.emptyText ? String(props.emptyText) : '暂无数据'} />
      }
      return (
        <List
          itemLayout="horizontal"
          dataSource={items}
          header={props.title as string}
          renderItem={(item) => (
            <List.Item key={item.id}>
              <List.Item.Meta
                title={
                  <div className="flex flex-col sm:flex-row sm:items-center sm:gap-3">
                    <span>{item.title}</span>
                    <Space size="small">
                      {item.status && <Tag color={statusColor(item.status)}>{item.status}</Tag>}
                      {item.tags?.map((tag) => (
                        <Tag key={`${item.id}-${tag.label}`} color={tag.color}>
                          {tag.label}
                        </Tag>
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
    }

    case 'Form': {
      const fields = props.fields as {
        name: string
        label: string
        type: string
        required?: boolean
        placeholder?: string
        options?: { label: string; value: string }[]
      }[]
      return (
        <Form layout="vertical">
          {fields?.map((field) => (
            <Form.Item key={field.name} label={field.label} required={field.required}>
              {renderFormField(field)}
            </Form.Item>
          ))}
          <Button type="primary">{(props.submitLabel as string) || '提交'}</Button>
        </Form>
      )
    }

    case 'Tag':
      return <Tag color={(props.color as string) || 'blue'}>{props.label as string}</Tag>

    case 'Chart':
      return (
        <Card size="small" title={props.title as string}>
          <ReactEChartsCore
            echarts={echarts}
            option={(props.option as Record<string, unknown>) || {}}
            style={{ height: 320 }}
          />
        </Card>
      )

    default:
      return <Empty description={`暂不支持的UI类型: ${type}`} />
  }
}

function renderFormField(field: {
  type: string
  placeholder?: string
  options?: { label: string; value: string }[]
}) {
  switch (field.type) {
    case 'number':
      return <InputNumber className="w-full" placeholder={field.placeholder} />
    case 'date':
      return <DatePicker className="w-full" placeholder={field.placeholder} />
    case 'select':
      return (
        <Select placeholder={field.placeholder}>
          {field.options?.map((option) => (
            <Select.Option key={option.value} value={option.value}>
              {option.label}
            </Select.Option>
          ))}
        </Select>
      )
    default:
      return <Input placeholder={field.placeholder} />
  }
}

function renderActions(actions?: UIAction[]) {
  if (!actions?.length) return null
  return (
    <Space size="small">
      {actions.map((action, index) => (
        <Button key={`${action.type}-${index}`} size="small" onClick={() => logAction(action)}>
          {action.label ?? action.type}
        </Button>
      ))}
    </Space>
  )
}

function logAction(action: UIAction) {
  if (action.type === 'open_link' && action.url) {
    window.open(action.url, '_blank', 'noopener')
    return
  }
  console.info('UI Action', action)
}

function statusColor(status: string) {
  if (status.includes('待')) return 'gold'
  if (status.includes('完成')) return 'green'
  if (status.includes('异常') || status.includes('失败')) return 'red'
  return 'blue'
}
