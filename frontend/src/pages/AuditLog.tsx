import { useState } from 'react'
import { Card, Table, Select, DatePicker, Space, Tag, Input } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { auditAPI } from '../services/api'
import type { AuditLogEntry } from '../types'

const { RangePicker } = DatePicker

const intentColors: Record<string, string> = {
  chat: 'blue',
  knowledge: 'green',
  data_query: 'orange',
  task_operation: 'purple',
}

const statusColors: Record<string, string> = {
  success: 'green',
  error: 'red',
  timeout: 'orange',
}

const columns = [
  {
    title: '用户ID',
    dataIndex: 'userId',
    key: 'userId',
    width: 120,
    ellipsis: true,
  },
  {
    title: '意图',
    dataIndex: 'intent',
    key: 'intent',
    width: 120,
    render: (intent: string) => (
      <Tag color={intentColors[intent] || 'default'}>{intent}</Tag>
    ),
  },
  {
    title: '模型',
    dataIndex: 'model',
    key: 'model',
    width: 140,
  },
  {
    title: '输入Token',
    dataIndex: 'inputTokens',
    key: 'inputTokens',
    width: 100,
    align: 'right' as const,
  },
  {
    title: '输出Token',
    dataIndex: 'outputTokens',
    key: 'outputTokens',
    width: 100,
    align: 'right' as const,
  },
  {
    title: '延迟(ms)',
    dataIndex: 'latencyMs',
    key: 'latencyMs',
    width: 100,
    align: 'right' as const,
    render: (ms: number) => (
      <span className={ms > 5000 ? 'text-red-500' : ''}>{ms}</span>
    ),
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 80,
    render: (status: string) => (
      <Tag color={statusColors[status] || 'default'}>{status}</Tag>
    ),
  },
  {
    title: '时间',
    dataIndex: 'createdAt',
    key: 'createdAt',
    width: 180,
  },
]

export default function AuditLog() {
  const [filters, setFilters] = useState<{
    userId?: string
    intent?: string
    status?: string
    startDate?: string
    endDate?: string
    page: number
    size: number
  }>({ page: 1, size: 20 })

  const { data, isLoading } = useQuery({
    queryKey: ['auditLogs', filters],
    queryFn: () => auditAPI.logs(filters).then((r) => r.data.data),
    staleTime: 10_000,
  })

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">审计日志</h2>

      <Card className="mb-4">
        <Space wrap>
          <Input
            placeholder="用户ID"
            allowClear
            style={{ width: 160 }}
            onChange={(e) =>
              setFilters((f) => ({ ...f, userId: e.target.value || undefined, page: 1 }))
            }
          />
          <Select
            placeholder="意图类型"
            allowClear
            style={{ width: 140 }}
            onChange={(v) => setFilters((f) => ({ ...f, intent: v, page: 1 }))}
            options={[
              { label: '对话', value: 'chat' },
              { label: '知识检索', value: 'knowledge' },
              { label: '数据查询', value: 'data_query' },
              { label: '任务操作', value: 'task_operation' },
            ]}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 120 }}
            onChange={(v) => setFilters((f) => ({ ...f, status: v, page: 1 }))}
            options={[
              { label: '成功', value: 'success' },
              { label: '失败', value: 'error' },
              { label: '超时', value: 'timeout' },
            ]}
          />
          <RangePicker
            onChange={(dates) => {
              if (dates && dates[0] && dates[1]) {
                setFilters((f) => ({
                  ...f,
                  startDate: dates[0]!.format('YYYY-MM-DD'),
                  endDate: dates[1]!.format('YYYY-MM-DD'),
                  page: 1,
                }))
              } else {
                setFilters((f) => ({ ...f, startDate: undefined, endDate: undefined, page: 1 }))
              }
            }}
          />
        </Space>
      </Card>

      <Card>
        <Table<AuditLogEntry>
          columns={columns}
          dataSource={data?.records ?? data?.data ?? []}
          rowKey="id"
          loading={isLoading}
          pagination={{
            current: filters.page,
            pageSize: filters.size,
            total: data?.total ?? 0,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, size) => setFilters((f) => ({ ...f, page, size })),
          }}
          scroll={{ x: 1000 }}
        />
      </Card>
    </div>
  )
}
