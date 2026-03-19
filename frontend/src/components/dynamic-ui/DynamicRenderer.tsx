import { Card, Table, Empty, List, Tag, Statistic, Form, Input, DatePicker, InputNumber, Select } from 'antd'
import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent, CanvasRenderer])

/**
 * 动态UI渲染组件 — 基于 json-render 规范
 *
 * 文档要求: json-render (Vercel Labs 生成式UI框架)
 * 组件目录: Card, Table, Metric, List, Form, Tag, Chart
 *
 * AI网关输出 JSON Spec → 本组件解析渲染
 * TODO: Sprint 5 时集成 @json-render/react 的 defineCatalog + Renderer
 */

// json-render 兼容的 UI Spec 类型定义
interface UISpec {
  type: 'Card' | 'Table' | 'Metric' | 'List' | 'Form' | 'Tag' | 'Chart'
  props?: Record<string, unknown>
  children?: UISpec[]
}

interface DynamicRendererProps {
  spec: UISpec | null
}

export default function DynamicRenderer({ spec }: DynamicRendererProps) {
  if (!spec) return null
  return renderNode(spec)
}

function renderNode(node: UISpec): React.ReactElement {
  const { type, props = {}, children } = node

  switch (type) {
    case 'Card':
      return (
        <Card title={props.title as string} className="mt-4">
          {children?.map((child, i) => <div key={i}>{renderNode(child)}</div>)}
        </Card>
      )

    case 'Table':
      return (
        <Table
          columns={(props.columns as string[])?.map((col) => ({
            title: col,
            dataIndex: col,
            key: col,
          }))}
          dataSource={(props.data as unknown[][])?.map((row, i) => {
            const obj: Record<string, unknown> = { key: i }
            ;(props.columns as string[])?.forEach((col, j) => {
              obj[col] = row[j]
            })
            return obj
          })}
          title={() => (props.title as string) || undefined}
          pagination={false}
          size="small"
        />
      )

    case 'Metric':
      return (
        <Statistic
          title={props.label as string}
          value={props.value as string}
          suffix={props.format === 'percent' ? '%' : undefined}
          prefix={props.format === 'currency' ? '¥' : undefined}
        />
      )

    case 'List':
      return (
        <List
          dataSource={props.items as { id: string; title: string; description?: string; status?: string }[]}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta
                title={item.title}
                description={item.description}
              />
              {item.status && <Tag>{item.status}</Tag>}
            </List.Item>
          )}
        />
      )

    case 'Form': {
      const fields = props.fields as { name: string; label: string; type: string; required: boolean }[]
      return (
        <Form layout="vertical">
          {fields?.map((field) => (
            <Form.Item key={field.name} label={field.label} required={field.required}>
              {field.type === 'number' ? <InputNumber className="w-full" /> :
               field.type === 'date' ? <DatePicker className="w-full" /> :
               field.type === 'select' ? <Select /> :
               <Input />}
            </Form.Item>
          ))}
        </Form>
      )
    }

    case 'Tag':
      return <Tag color={(props.color as string) || 'blue'}>{props.label as string}</Tag>

    case 'Chart':
      return (
        <ReactEChartsCore
          echarts={echarts}
          option={props.option as Record<string, unknown> || {}}
          style={{ height: 300 }}
        />
      )

    default:
      return <Empty description={`暂不支持的UI类型: ${type}`} />
  }
}
