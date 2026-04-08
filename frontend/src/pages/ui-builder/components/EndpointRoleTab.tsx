import { useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  List,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'

import { formatDateTime } from '../helpers'
import type {
  UiApiEndpoint,
  UiApiEndpointRole,
  UiApiEndpointRoleBindRequest,
  UiApiSource,
  UiRole,
} from '../types'

interface EndpointRoleTabProps {
  roles: UiRole[]
  sources: UiApiSource[]
  relations: UiApiEndpointRole[]
  selectedRoleId?: string
  loading: boolean
  relationPagination: {
    current: number
    pageSize: number
    total: number
  }
  onSelectRole: (roleId: string) => void
  onRelationPageChange: (page: number, size: number) => void
  onRefreshRoles: () => Promise<void>
  onLoadEndpointsBySource: (sourceId: string) => Promise<UiApiEndpoint[]>
  onBindRelations: (payload: UiApiEndpointRoleBindRequest) => Promise<void>
  onDeleteRelation: (relationId: string) => Promise<void>
}

const DEFAULT_APP_CODE = 'AI-RND-WORKFLOW'

export function EndpointRoleTab({
  roles,
  sources,
  relations,
  selectedRoleId,
  loading,
  relationPagination,
  onSelectRole,
  onRelationPageChange,
  onRefreshRoles,
  onLoadEndpointsBySource,
  onBindRelations,
  onDeleteRelation,
}: EndpointRoleTabProps) {
  const [messageApi, contextHolder] = message.useMessage()
  const [bindModalOpen, setBindModalOpen] = useState(false)
  const [loadingEndpoints, setLoadingEndpoints] = useState(false)
  const [availableEndpoints, setAvailableEndpoints] = useState<UiApiEndpoint[]>([])
  const [bindForm] = Form.useForm<{
    roleName: string
    sourceId?: string
    endpointIds: string[]
  }>()

  const selectedRole = useMemo(
    () => roles.find((item) => item.id === selectedRoleId),
    [roles, selectedRoleId],
  )

  const endpointOptions = useMemo(
    () =>
      availableEndpoints.map((endpoint) => ({
        label: `${endpoint.method} ${endpoint.name} (${endpoint.path})`,
        value: endpoint.id,
      })),
    [availableEndpoints],
  )

  useEffect(() => {
    if (!bindModalOpen || !selectedRole) {
      return
    }
    bindForm.setFieldsValue({
      roleName: selectedRole.roleName,
      sourceId: undefined,
      endpointIds: [],
    })
    setAvailableEndpoints([])
  }, [bindForm, bindModalOpen, selectedRole])

  const relationColumns = useMemo<TableColumnsType<UiApiEndpointRole>>(() => ([
    {
      title: '方法',
      dataIndex: 'endpointMethod',
      key: 'endpointMethod',
      width: 96,
      render: (value?: string | null) => value ? (
        <Tag color={value === 'GET' ? 'blue' : value === 'POST' ? 'green' : 'purple'}>{value}</Tag>
      ) : '-',
    },
    {
      title: '接口定义',
      key: 'endpointName',
      render: (_, record) => (
        <div>
          <div className="font-medium text-slate-900">{record.endpointName ?? '接口已删除'}</div>
          <div className="text-xs text-slate-500">{record.endpointPath ?? '-'}</div>
        </div>
      ),
    },
    {
      title: '接口源',
      dataIndex: 'sourceName',
      key: 'sourceName',
      width: 160,
      render: (value?: string | null) => value ?? '-',
    },
    {
      title: '标签',
      dataIndex: 'tagName',
      key: 'tagName',
      width: 140,
      render: (value?: string | null) => value ? <Tag color="cyan">{value}</Tag> : <Tag>未分组</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'endpointStatus',
      key: 'endpointStatus',
      width: 100,
      render: (value?: string | null) => (
        <Tag color={value === 'active' ? 'green' : 'default'}>{value ?? 'unknown'}</Tag>
      ),
    },
    {
      title: '关联时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 180,
      render: (value?: string | null) => formatDateTime(value),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Popconfirm title="移除这条接口角色关系？" onConfirm={() => onDeleteRelation(record.id)}>
          <Button danger size="small">
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ]), [onDeleteRelation])

  async function handleSourceChange(sourceId: string) {
    bindForm.setFieldValue('endpointIds', [])
    setLoadingEndpoints(true)
    try {
      const endpointList = await onLoadEndpointsBySource(sourceId)
      setAvailableEndpoints(endpointList)
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : '加载接口定义失败')
    } finally {
      setLoadingEndpoints(false)
    }
  }

  async function handleSubmit() {
    if (!selectedRole) {
      return
    }
    const values = await bindForm.validateFields()
    await onBindRelations({
      roleId: selectedRole.id,
      roleCode: selectedRole.roleCode,
      roleName: selectedRole.roleName,
      endpointIds: values.endpointIds,
      createdBy: 'ui-builder',
    })
    setBindModalOpen(false)
    setAvailableEndpoints([])
    bindForm.resetFields()
  }

  return (
    <>
      {contextHolder}
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Card
          title="角色列表"
          extra={(
            <Button onClick={() => void onRefreshRoles()} size="small">
              刷新角色
            </Button>
          )}
          className="rounded-[24px]"
        >
          {roles.length ? (
            <List
              dataSource={roles}
              renderItem={(role) => (
                <List.Item style={{ border: 'none', padding: 0, marginBottom: 12 }}>
                  <button
                    className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                      role.id === selectedRoleId
                        ? 'border-sky-300 bg-sky-50'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    }`}
                    onClick={() => onSelectRole(role.id)}
                    type="button"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium text-slate-900">{role.roleName}</div>
                        <div className="text-xs text-slate-500">{role.roleCode || role.id}</div>
                      </div>
                      <Tag color={role.status === 1 ? 'green' : 'default'}>
                        {role.status === 1 ? '启用' : '未知'}
                      </Tag>
                    </div>
                    <div className="mt-2 text-xs text-slate-500">{role.appCode || DEFAULT_APP_CODE}</div>
                  </button>
                </List.Item>
              )}
            />
          ) : (
            <Empty description="没有加载到角色" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Card>

        <div className="space-y-5">
          <Card
            title="角色接口关系"
            extra={(
              <Space>
                <Button disabled={!selectedRole} onClick={() => setBindModalOpen(true)} type="primary">
                  关联接口
                </Button>
              </Space>
            )}
            className="rounded-[24px]"
          >
            {selectedRole ? (
              <Descriptions size="small" column={3}>
                <Descriptions.Item label="角色名称">{selectedRole.roleName}</Descriptions.Item>
                <Descriptions.Item label="角色编码">{selectedRole.roleCode || '-'}</Descriptions.Item>
                <Descriptions.Item label="应用编码">{selectedRole.appCode || DEFAULT_APP_CODE}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Empty description="请选择一个角色后查看已关联接口" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>

          <Card className="rounded-[24px]">
            <Table<UiApiEndpointRole>
              rowKey="id"
              loading={loading}
              dataSource={relations}
              columns={relationColumns}
              pagination={{
                current: relationPagination.current,
                pageSize: relationPagination.pageSize,
                total: relationPagination.total,
                onChange: onRelationPageChange,
              }}
              locale={{
                emptyText: selectedRole
                  ? '当前角色还没有关联接口'
                  : '请选择左侧角色后查看接口关系',
              }}
            />
          </Card>
        </div>
      </div>

      <Modal
        destroyOnClose
        forceRender
        open={bindModalOpen}
        title="关联接口到角色"
        onCancel={() => setBindModalOpen(false)}
        onOk={() => void handleSubmit()}
        okText="保存关联"
      >
        {!selectedRole ? (
          <Empty description="请先选择角色" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <Form form={bindForm} layout="vertical">
            <Form.Item label="当前角色" name="roleName">
              <Input disabled />
            </Form.Item>
            <Form.Item
              label="接口源"
              name="sourceId"
              rules={[{ required: true, message: '请选择接口源' }]}
            >
              <Select
                options={sources.map((source) => ({ label: `${source.name} (${source.code})`, value: source.id }))}
                placeholder="先选择接口源，再选择接口定义"
                onChange={(value) => void handleSourceChange(value)}
              />
            </Form.Item>
            <Form.Item
              label="接口定义"
              name="endpointIds"
              rules={[{ required: true, message: '请选择至少一个接口定义' }]}
              extra="这里只展示当前接口源下已经存在的接口定义。"
            >
              <Select
                mode="multiple"
                showSearch
                loading={loadingEndpoints}
                options={endpointOptions}
                optionFilterProp="label"
                placeholder="选择要关联到当前角色的接口定义"
              />
            </Form.Item>
            {!availableEndpoints.length && bindForm.getFieldValue('sourceId') ? (
              <Typography.Text type="secondary">
                当前接口源下暂无可选接口，请先到“接口中心”导入或创建接口定义。
              </Typography.Text>
            ) : null}
          </Form>
        )}
      </Modal>
    </>
  )
}
