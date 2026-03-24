import { Card, Row, Col, Statistic, List, Tag, Spin, Alert } from 'antd'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  MessageOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { taskAPI, documentAPI } from '../services/api'

interface TaskItem {
  id: string
  title: string
  source_system: string
  priority: string
  status: string
}

export default function Workspace() {
  const {
    data: taskData,
    isLoading: taskLoading,
    error: taskError,
  } = useQuery({
    queryKey: ['tasks', 'aggregate'],
    queryFn: () => taskAPI.aggregate({ page: 1, size: 20 }).then((res) => res.data),
    staleTime: 30_000,
  })

  const {
    data: docData,
    isLoading: docLoading,
  } = useQuery({
    queryKey: ['documents', 'count'],
    queryFn: () => documentAPI.list(1, 1).then((res) => res.data),
    staleTime: 60_000,
  })

  const tasks: TaskItem[] = taskData?.data?.records ?? taskData?.data ?? []
  const totalTasks = taskData?.data?.total ?? tasks.length
  const completedTasks = tasks.filter((t) => t.status === 'completed').length
  const pendingTasks = totalTasks - completedTasks
  const docCount = docData?.data?.total ?? 0

  const loading = taskLoading || docLoading

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">统一工作台</h2>

      {taskError && (
        <Alert
          type="warning"
          message="数据加载失败，显示的可能是缓存数据"
          className="mb-4"
          closable
        />
      )}

      <Spin spinning={loading}>
        <Row gutter={16} className="mb-6">
          <Col span={6}>
            <Card>
              <Statistic title="待办任务" value={pendingTasks} prefix={<ClockCircleOutlined />} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="已完成" value={completedTasks} prefix={<CheckCircleOutlined />} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="知识文档" value={docCount} prefix={<FileTextOutlined />} />
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
            dataSource={tasks.filter((t) => t.status !== 'completed')}
            locale={{ emptyText: '暂无待办任务，试试在左侧AI对话中询问' }}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={item.title}
                  description={<Tag>{item.source_system}</Tag>}
                />
                <Tag color={item.priority === 'high' ? 'red' : item.priority === 'medium' ? 'orange' : 'blue'}>
                  {item.priority}
                </Tag>
              </List.Item>
            )}
          />
        </Card>
      </Spin>
    </div>
  )
}
