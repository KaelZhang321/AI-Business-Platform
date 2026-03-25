import { useState } from 'react'
import { Card, Table, Button, Space, Tag, Alert, Spin } from 'antd'
import { UploadOutlined, SearchOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { documentAPI } from '../services/api'
import type { KnowledgeDocument } from '../types'

const statusColors: Record<string, string> = {
  pending: 'default',
  processing: 'processing',
  processed: 'success',
  failed: 'error',
}

const columns = [
  { title: '文档标题', dataIndex: 'title', key: 'title' },
  { title: '分类', dataIndex: 'category', key: 'category', width: 120 },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 100,
    render: (status: string) => <Tag color={statusColors[status] || 'default'}>{status}</Tag>,
  },
  { title: '分块数', dataIndex: 'chunkCount', key: 'chunkCount', width: 80, align: 'right' as const },
  { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt', width: 180 },
]

export default function KnowledgeBase() {
  const [pagination, setPagination] = useState({ page: 1, size: 20 })

  const { data, isLoading, error } = useQuery({
    queryKey: ['documents', pagination],
    queryFn: () => documentAPI.list(pagination).then((r) => r.data.data),
    staleTime: 60_000,
  })

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">知识库管理</h2>
        <Space>
          <Button icon={<SearchOutlined />}>检索测试</Button>
          <Button type="primary" icon={<UploadOutlined />}>上传文档</Button>
        </Space>
      </div>

      {error && (
        <Alert
          type="warning"
          message="数据加载失败，显示的可能是缓存数据"
          className="mb-4"
          closable
        />
      )}

      <Spin spinning={isLoading}>
        <Card>
          <Table<KnowledgeDocument>
            columns={columns}
            dataSource={data?.records ?? data?.data ?? []}
            rowKey="id"
            locale={{ emptyText: '暂无文档，请点击上传文档按钮添加' }}
            pagination={{
              current: pagination.page,
              pageSize: pagination.size,
              total: data?.total ?? 0,
              showSizeChanger: true,
              showTotal: (total) => `共 ${total} 条`,
              onChange: (page, size) => setPagination({ page, size }),
            }}
          />
        </Card>
      </Spin>
    </div>
  )
}
