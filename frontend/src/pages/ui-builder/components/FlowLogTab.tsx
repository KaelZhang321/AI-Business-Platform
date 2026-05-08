import { useMemo, useState } from 'react'
import { Button, Card, Descriptions, Drawer, Form, Input, Select, Space, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'

import { formatDateTime, prettyJson } from '../helpers'
import type { UiApiFlowLog } from '../types'

interface FlowLogTabProps {
  logs: UiApiFlowLog[]
  loading: boolean
  filters: {
    flowNum: string
    requestUrl: string
    createdBy: string
    invokeStatus: string
  }
  pagination: {
    current: number
    pageSize: number
    total: number
  }
  onFlowNumChange: (value: string) => void
  onRequestUrlChange: (value: string) => void
  onCreatedByChange: (value: string) => void
  onInvokeStatusChange: (value: string) => void
  onPageChange: (page: number, size: number) => void
}

const invokeStatusOptions = [
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '超时', value: 'timeout' },
]

function renderStatus(status?: string | null) {
  if (status === 'success') {
    return <Tag color="green">success</Tag>
  }
  if (status === 'failed') {
    return <Tag color="red">failed</Tag>
  }
  if (status === 'timeout') {
    return <Tag color="orange">timeout</Tag>
  }
  return <Tag>{status || 'unknown'}</Tag>
}

export function FlowLogTab({
  logs,
  loading,
  filters,
  pagination,
  onFlowNumChange,
  onRequestUrlChange,
  onCreatedByChange,
  onInvokeStatusChange,
  onPageChange,
}: FlowLogTabProps) {
  const [selectedLog, setSelectedLog] = useState<UiApiFlowLog | null>(null)

  const columns = useMemo<TableColumnsType<UiApiFlowLog>>(() => ([
    {
      title: '流程号',
      dataIndex: 'flowNum',
      key: 'flowNum',
      width: 220,
      render: (value: string | null | undefined, record) => (
        <div className="space-y-1">
          <div className="font-medium text-slate-900">{value || '-'}</div>
          <div className="text-xs text-slate-500 break-all">{record.id}</div>
        </div>
      ),
    },
    {
      title: '请求地址',
      dataIndex: 'requestUrl',
      key: 'requestUrl',
      ellipsis: true,
      render: (value: string | null | undefined) => (
        <Typography.Text ellipsis={{ tooltip: value || '-' }}>
          {value || '-'}
        </Typography.Text>
      ),
    },
    {
      title: '创建人',
      key: 'createdBy',
      width: 180,
      render: (_, record) => (
        <div>
          <div>{record.createdByName || '-'}</div>
          <div className="text-xs text-slate-500">{record.createdBy || '-'}</div>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'invokeStatus',
      key: 'invokeStatus',
      width: 120,
      render: (value: string | null | undefined) => renderStatus(value),
    },
    {
      title: '时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 190,
      render: (value: string | null | undefined) => formatDateTime(value),
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_, record) => (
        <Button type="link" onClick={() => setSelectedLog(record)}>
          查看
        </Button>
      ),
    },
  ]), [])

  return (
    <div className="space-y-6">
      <Card
        title="调用日志筛选"
        className="rounded-[24px]"
      >
        <Form layout="vertical">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Form.Item label="流程号" style={{ marginBottom: 0 }}>
              <Input
                allowClear
                placeholder="按 flowNum 搜索"
                value={filters.flowNum}
                onChange={(event) => onFlowNumChange(event.target.value)}
              />
            </Form.Item>
            <Form.Item label="请求地址" style={{ marginBottom: 0 }}>
              <Input
                allowClear
                placeholder="按 request_url 搜索"
                value={filters.requestUrl}
                onChange={(event) => onRequestUrlChange(event.target.value)}
              />
            </Form.Item>
            <Form.Item label="创建人" style={{ marginBottom: 0 }}>
              <Input
                allowClear
                placeholder="按 create_by 搜索"
                value={filters.createdBy}
                onChange={(event) => onCreatedByChange(event.target.value)}
              />
            </Form.Item>
            <Form.Item label="调用状态" style={{ marginBottom: 0 }}>
              <Select
                allowClear
                options={invokeStatusOptions}
                placeholder="全部状态"
                value={filters.invokeStatus}
                onChange={(value) => onInvokeStatusChange(value ?? '')}
              />
            </Form.Item>
          </div>
        </Form>
      </Card>

      <Card title="运行时调用日志" className="rounded-[24px]">
        <Table<UiApiFlowLog>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={logs}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            onChange: onPageChange,
            onShowSizeChange: onPageChange,
            showSizeChanger: true,
          }}
          scroll={{ x: 1080 }}
        />
      </Card>

      <Drawer
        title="调用日志详情"
        width={760}
        open={!!selectedLog}
        onClose={() => setSelectedLog(null)}
      >
        {selectedLog ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions bordered size="small" column={1}>
              <Descriptions.Item label="流程号">{selectedLog.flowNum || '-'}</Descriptions.Item>
              <Descriptions.Item label="接口ID">{selectedLog.endpointId || '-'}</Descriptions.Item>
              <Descriptions.Item label="创建人">
                {selectedLog.createdByName || '-'} / {selectedLog.createdBy || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="调用状态">{selectedLog.invokeStatus || '-'}</Descriptions.Item>
              <Descriptions.Item label="响应状态码">{selectedLog.responseStatus ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="请求地址">{selectedLog.requestUrl || '-'}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{formatDateTime(selectedLog.createdAt)}</Descriptions.Item>
              <Descriptions.Item label="错误信息">{selectedLog.errorMessage || '-'}</Descriptions.Item>
            </Descriptions>

            <Card size="small" title="请求头">
              <pre className="whitespace-pre-wrap break-all text-xs text-slate-700">{prettyJson(selectedLog.requestHeaders)}</pre>
            </Card>
            <Card size="small" title="Query 参数">
              <pre className="whitespace-pre-wrap break-all text-xs text-slate-700">{prettyJson(selectedLog.requestQuery)}</pre>
            </Card>
            <Card size="small" title="请求体">
              <pre className="whitespace-pre-wrap break-all text-xs text-slate-700">{prettyJson(selectedLog.requestBody)}</pre>
            </Card>
            <Card size="small" title="响应头">
              <pre className="whitespace-pre-wrap break-all text-xs text-slate-700">{prettyJson(selectedLog.responseHeaders)}</pre>
            </Card>
            <Card size="small" title="响应体">
              <pre className="whitespace-pre-wrap break-all text-xs text-slate-700">{prettyJson(selectedLog.responseBody)}</pre>
            </Card>
          </Space>
        ) : null}
      </Drawer>
    </div>
  )
}
