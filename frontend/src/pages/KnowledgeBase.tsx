import { Card, Table, Button, Space } from 'antd'
import { UploadOutlined, SearchOutlined } from '@ant-design/icons'

const columns = [
  { title: '文档标题', dataIndex: 'title', key: 'title' },
  { title: '类型', dataIndex: 'docType', key: 'docType' },
  { title: '向量化状态', dataIndex: 'embeddingStatus', key: 'embeddingStatus' },
  { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt' },
]

export default function KnowledgeBase() {
  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">知识库管理</h2>
        <Space>
          <Button icon={<SearchOutlined />}>检索测试</Button>
          <Button type="primary" icon={<UploadOutlined />}>上传文档</Button>
        </Space>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={[]}
          locale={{ emptyText: '暂无文档，请点击上传文档按钮添加' }}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  )
}
