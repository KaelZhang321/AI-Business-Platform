import { Card, Row, Col, Statistic, List, Tag } from 'antd'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  MessageOutlined,
} from '@ant-design/icons'

export default function Workspace() {
  return (
    <div>
      <h2 className="text-xl font-bold mb-4">统一工作台</h2>

      <Row gutter={16} className="mb-6">
        <Col span={6}>
          <Card>
            <Statistic title="待办任务" value={0} prefix={<ClockCircleOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="已完成" value={0} prefix={<CheckCircleOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="知识文档" value={0} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="今日对话" value={0} prefix={<MessageOutlined />} />
          </Card>
        </Col>
      </Row>

      <Card title="待办任务" className="mb-6">
        <List
          dataSource={[]}
          locale={{ emptyText: '暂无待办任务，试试在左侧AI对话中询问' }}
          renderItem={(item: { title: string; source: string; priority: string }) => (
            <List.Item>
              <List.Item.Meta title={item.title} description={<Tag>{item.source}</Tag>} />
            </List.Item>
          )}
        />
      </Card>
    </div>
  )
}
