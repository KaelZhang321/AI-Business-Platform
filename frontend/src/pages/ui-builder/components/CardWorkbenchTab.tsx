import { useMemo, useState } from 'react'
import {
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { TableColumnsType } from 'antd'

import { formatDateTime } from '../helpers'
import type {
  UiApiEndpoint,
  UiCard,
  UiCardEndpointRelation,
  UiCardRequest,
  UiApiSource,
} from '../types'

interface CardWorkbenchTabProps {
  cards: UiCard[]
  relations: UiCardEndpointRelation[]
  sources: UiApiSource[]
  selectedCardId?: string
  loading: boolean
  cardPagination: {
    current: number
    pageSize: number
    total: number
  }
  relationPagination: {
    current: number
    pageSize: number
    total: number
  }
  onSelectCard: (cardId: string) => void
  onCardPageChange: (page: number, size: number) => void
  onRelationPageChange: (page: number, size: number) => void
  onSaveCard: (cardId: string | undefined, payload: UiCardRequest) => Promise<void>
  onDeleteCard: (cardId: string) => Promise<void>
  onBindRelations: (cardId: string, endpointIds: string[]) => Promise<void>
  onDeleteRelation: (cardId: string, relationId: string) => Promise<void>
  onLoadEndpointsBySource: (sourceId: string) => Promise<UiApiEndpoint[]>
}

const cardStatusOptions = [
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' },
]

export function CardWorkbenchTab({
  cards,
  relations,
  sources,
  selectedCardId,
  loading,
  cardPagination,
  relationPagination,
  onSelectCard,
  onCardPageChange,
  onRelationPageChange,
  onSaveCard,
  onDeleteCard,
  onBindRelations,
  onDeleteRelation,
  onLoadEndpointsBySource,
}: CardWorkbenchTabProps) {
  const [cardModalOpen, setCardModalOpen] = useState(false)
  const [bindModalOpen, setBindModalOpen] = useState(false)
  const [editingCard, setEditingCard] = useState<UiCard | null>(null)
  const [bindLoading, setBindLoading] = useState(false)
  const [endpointLoading, setEndpointLoading] = useState(false)
  const [availableEndpoints, setAvailableEndpoints] = useState<UiApiEndpoint[]>([])

  const [cardForm] = Form.useForm<UiCardRequest>()
  const [bindForm] = Form.useForm<{ sourceId?: string; endpointIds?: string[] }>()

  const selectedCard = useMemo(
    () => cards.find((item) => item.id === selectedCardId),
    [cards, selectedCardId],
  )

  const cardColumns = useMemo<TableColumnsType<UiCard>>(() => ([
    {
      title: '卡片',
      key: 'card',
      render: (_, record) => (
        <button
          className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
            record.id === selectedCardId
              ? 'border-sky-300 bg-sky-50'
              : 'border-slate-200 bg-white hover:border-slate-300'
          }`}
          onClick={() => onSelectCard(record.id)}
          type="button"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="font-medium text-slate-900">{record.name}</div>
              <div className="text-xs text-slate-500">{record.code}</div>
            </div>
            <Tag color={record.status === 'active' ? 'green' : 'default'}>{record.status || 'active'}</Tag>
          </div>
          <div className="mt-1 text-xs text-slate-400">{record.cardType || 'json_render'}</div>
        </button>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 130,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" onClick={() => openCardModal(record)}>编辑</Button>
          <Popconfirm title="删除卡片？" onConfirm={() => onDeleteCard(record.id)}>
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [onDeleteCard, onSelectCard, selectedCardId])

  const relationColumns = useMemo<TableColumnsType<UiCardEndpointRelation>>(() => ([
    {
      title: '方法',
      dataIndex: 'endpointMethod',
      key: 'endpointMethod',
      width: 100,
      render: (value?: string | null) => value ? <Tag color={value === 'GET' ? 'blue' : 'green'}>{value}</Tag> : '-',
    },
    {
      title: '接口名称',
      dataIndex: 'endpointName',
      key: 'endpointName',
      width: 200,
      render: (value?: string | null, record) => (
        <div>
          <div className="font-medium text-slate-900">{value || '-'}</div>
          <div className="text-xs text-slate-500 break-all">{record.endpointId}</div>
        </div>
      ),
    },
    {
      title: '路径',
      dataIndex: 'endpointPath',
      key: 'endpointPath',
      ellipsis: true,
    },
    {
      title: '接口源',
      dataIndex: 'sourceName',
      key: 'sourceName',
      width: 140,
      render: (value?: string | null) => value || '-',
    },
    {
      title: '标签',
      dataIndex: 'tagName',
      key: 'tagName',
      width: 120,
      render: (value?: string | null) => value ? <Tag color="cyan">{value}</Tag> : <Tag>未分组</Tag>,
    },
    {
      title: '排序',
      dataIndex: 'sortOrder',
      key: 'sortOrder',
      width: 90,
      render: (value?: number | null) => value ?? 0,
    },
    {
      title: '更新时间',
      dataIndex: 'updatedAt',
      key: 'updatedAt',
      width: 180,
      render: (value?: string | null) => formatDateTime(value),
    },
    {
      title: '操作',
      key: 'actions',
      width: 110,
      render: (_, record) => (
        <Popconfirm
          title="取消关联这个接口？"
          onConfirm={() => {
            if (!selectedCardId) {
              return
            }
            void onDeleteRelation(selectedCardId, record.id)
          }}
        >
          <Button size="small" danger>删除</Button>
        </Popconfirm>
      ),
    },
  ]), [onDeleteRelation, selectedCardId])

  function openCardModal(card?: UiCard) {
    setEditingCard(card ?? null)
    setCardModalOpen(true)
    cardForm.setFieldsValue({
      name: card?.name ?? '',
      code: card?.code ?? '',
      description: card?.description ?? '',
      cardType: card?.cardType ?? 'json_render',
      status: card?.status ?? 'active',
    })
  }

  function openBindModal() {
    if (!selectedCardId) {
      return
    }
    setBindModalOpen(true)
    setAvailableEndpoints([])
    bindForm.resetFields()
  }

  async function handleLoadSourceEndpoints(sourceId: string) {
    setEndpointLoading(true)
    try {
      const items = await onLoadEndpointsBySource(sourceId)
      setAvailableEndpoints(items)
    } finally {
      setEndpointLoading(false)
    }
  }

  async function handleSubmitCard() {
    const values = await cardForm.validateFields()
    await onSaveCard(editingCard?.id, values)
    setCardModalOpen(false)
    setEditingCard(null)
    cardForm.resetFields()
  }

  async function handleSubmitBind() {
    if (!selectedCardId) {
      return
    }
    const values = await bindForm.validateFields()
    setBindLoading(true)
    try {
      await onBindRelations(selectedCardId, values.endpointIds ?? [])
      setBindModalOpen(false)
      bindForm.resetFields()
      setAvailableEndpoints([])
    } finally {
      setBindLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={9}>
          <Card
            title="卡片列表"
            className="rounded-[24px]"
            extra={<Button type="primary" onClick={() => openCardModal()}>新建卡片</Button>}
          >
            <Table
              rowKey="id"
              loading={loading}
              dataSource={cards}
              columns={cardColumns}
              pagination={{
                current: cardPagination.current,
                pageSize: cardPagination.pageSize,
                total: cardPagination.total,
                showSizeChanger: true,
                onChange: onCardPageChange,
              }}
              locale={{ emptyText: <Empty description="暂无卡片" /> }}
            />
          </Card>
        </Col>
        <Col xs={24} xl={15}>
          <Card
            title={selectedCard ? `接口关联 · ${selectedCard.name}` : '接口关联'}
            className="rounded-[24px]"
            extra={(
              <Space>
                <Typography.Text type="secondary">{selectedCard?.code || '请先选择左侧卡片'}</Typography.Text>
                <Button type="primary" disabled={!selectedCardId} onClick={openBindModal}>
                  关联接口
                </Button>
              </Space>
            )}
          >
            {!selectedCardId ? (
              <Empty description="先从左侧选择一个卡片，再配置关联接口" />
            ) : (
              <Table
                rowKey="id"
                loading={loading}
                dataSource={relations}
                columns={relationColumns}
                pagination={{
                  current: relationPagination.current,
                  pageSize: relationPagination.pageSize,
                  total: relationPagination.total,
                  showSizeChanger: true,
                  onChange: onRelationPageChange,
                }}
                locale={{ emptyText: <Empty description="当前卡片还未关联接口" /> }}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title={editingCard ? '编辑卡片' : '新建卡片'}
        open={cardModalOpen}
        onCancel={() => {
          setCardModalOpen(false)
          setEditingCard(null)
          cardForm.resetFields()
        }}
        onOk={() => {
          void handleSubmitCard().catch(() => undefined)
        }}
        destroyOnClose
      >
        <Form form={cardForm} layout="vertical">
          <Form.Item name="name" label="卡片名称" rules={[{ required: true, message: '请输入卡片名称' }]}>
            <Input placeholder="例如：患者基础信息卡片" />
          </Form.Item>
          <Form.Item name="code" label="卡片编码" rules={[{ required: true, message: '请输入卡片编码' }]}>
            <Input placeholder="例如：patient_profile_card" />
          </Form.Item>
          <Form.Item name="description" label="卡片说明">
            <Input.TextArea rows={3} placeholder="可选，描述这个卡片的用途" />
          </Form.Item>
          <Form.Item name="cardType" label="卡片类型">
            <Input placeholder="默认 json_render" />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={cardStatusOptions} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="关联接口"
        open={bindModalOpen}
        onCancel={() => {
          setBindModalOpen(false)
          bindForm.resetFields()
          setAvailableEndpoints([])
        }}
        onOk={() => {
          void handleSubmitBind().catch(() => undefined)
        }}
        confirmLoading={bindLoading}
        destroyOnClose
      >
        <Form form={bindForm} layout="vertical">
          <Form.Item name="sourceId" label="接口源" rules={[{ required: true, message: '请选择接口源' }]}>
            <Select
              showSearch
              optionFilterProp="label"
              options={sources.map((item) => ({ label: `${item.name} (${item.code})`, value: item.id }))}
              placeholder="选择接口源后加载接口列表"
              onChange={(value) => {
                void handleLoadSourceEndpoints(value).catch(() => undefined)
              }}
            />
          </Form.Item>
          <Form.Item name="endpointIds" label="接口列表" rules={[{ required: true, message: '请至少选择一个接口' }]}>
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              loading={endpointLoading}
              placeholder={endpointLoading ? '正在加载接口...' : '请选择要关联的接口'}
              options={availableEndpoints.map((item) => ({
                label: `${item.method} ${item.name} (${item.path})`,
                value: item.id,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
