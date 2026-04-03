import { useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
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

import { formatDateTime, prettyJson } from '../helpers'
import type {
  UiApiEndpoint,
  UiBuilderNodeType,
  UiBuilderPageDetail,
  UiNodeBinding,
  UiNodeBindingRequest,
  UiPage,
  UiPageNode,
  UiPageNodeRequest,
  UiPagePreviewResponse,
  UiPageRequest,
  UiProject,
  UiProjectRequest,
} from '../types'

const EMPTY_NODE_FORM: UiPageNodeRequest = {
  parentId: undefined,
  nodeKey: '',
  nodeType: 'Card',
  nodeName: '',
  sortOrder: 0,
  slotName: 'default',
  propsConfig: '{}',
  styleConfig: '{}',
  status: 'active',
}

const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '发布', value: 'published' },
  { label: '停用', value: 'inactive' },
]

interface StudioTabProps {
  projects: UiProject[]
  pages: UiPage[]
  pageDetail?: UiBuilderPageDetail | null
  selectedProjectId?: string
  selectedPageId?: string
  preview?: UiPagePreviewResponse | null
  nodeTypes: UiBuilderNodeType[]
  endpoints: UiApiEndpoint[]
  loading: boolean
  projectPagination: {
    current: number
    pageSize: number
    total: number
  }
  pagePagination: {
    current: number
    pageSize: number
    total: number
  }
  onProjectPageChange: (page: number, size: number) => void
  onPagePageChange: (page: number, size: number) => void
  onSelectProject: (projectId: string) => void
  onSelectPage: (pageId: string) => void
  onSaveProject: (projectId: string | undefined, payload: UiProjectRequest) => Promise<void>
  onDeleteProject: (projectId: string) => Promise<void>
  onSavePage: (projectId: string, pageId: string | undefined, payload: UiPageRequest) => Promise<void>
  onDeletePage: (pageId: string) => Promise<void>
  onSaveNode: (pageId: string, nodeId: string | undefined, payload: UiPageNodeRequest) => Promise<void>
  onDeleteNode: (nodeId: string) => Promise<void>
  onSaveBinding: (nodeId: string, bindingId: string | undefined, payload: UiNodeBindingRequest) => Promise<void>
  onDeleteBinding: (bindingId: string) => Promise<void>
  onRefreshPreview: (pageId: string) => Promise<void>
}

export function StudioTab({
  projects,
  pages,
  pageDetail,
  selectedProjectId,
  selectedPageId,
  preview,
  nodeTypes,
  endpoints,
  loading,
  projectPagination,
  pagePagination,
  onProjectPageChange,
  onPagePageChange,
  onSelectProject,
  onSelectPage,
  onSaveProject,
  onDeleteProject,
  onSavePage,
  onDeletePage,
  onSaveNode,
  onDeleteNode,
  onSaveBinding,
  onDeleteBinding,
  onRefreshPreview,
}: StudioTabProps) {
  const [projectModalOpen, setProjectModalOpen] = useState(false)
  const [pageModalOpen, setPageModalOpen] = useState(false)
  const [nodeModalOpen, setNodeModalOpen] = useState(false)
  const [bindingModalOpen, setBindingModalOpen] = useState(false)
  const [editingProject, setEditingProject] = useState<UiProject | null>(null)
  const [editingPage, setEditingPage] = useState<UiPage | null>(null)
  const [editingNode, setEditingNode] = useState<UiPageNode | null>(null)
  const [editingBinding, setEditingBinding] = useState<UiNodeBinding | null>(null)
  const [bindingNodeId, setBindingNodeId] = useState<string | null>(null)

  const [projectForm] = Form.useForm<UiProjectRequest>()
  const [pageForm] = Form.useForm<UiPageRequest>()
  const [nodeForm] = Form.useForm<UiPageNodeRequest>()
  const [bindingForm] = Form.useForm<UiNodeBindingRequest>()

  const selectedProject = useMemo(
    () => projects.find((item) => item.id === selectedProjectId),
    [projects, selectedProjectId],
  )
  const selectedPage = useMemo(
    () => pages.find((item) => item.id === selectedPageId),
    [pages, selectedPageId],
  )
  const nodes = pageDetail?.nodes ?? []
  const bindings = pageDetail?.bindings ?? []

  const nodeNameById = useMemo(() => {
    const map = new Map<string, string>()
    nodes.forEach((node) => {
      map.set(node.id, node.nodeName)
    })
    return map
  }, [nodes])

  const projectColumns = useMemo<TableColumnsType<UiProject>>(() => ([
    {
      title: '项目',
      key: 'project',
      render: (_, record) => (
        <button
          className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
            record.id === selectedProjectId
              ? 'border-sky-300 bg-sky-50'
              : 'border-slate-200 bg-white hover:border-slate-300'
          }`}
          onClick={() => onSelectProject(record.id)}
          type="button"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="font-medium text-slate-900">{record.name}</div>
              <div className="text-xs text-slate-500">{record.code}</div>
            </div>
            <Tag color={record.status === 'published' ? 'green' : 'default'}>{record.status ?? 'draft'}</Tag>
          </div>
        </button>
      ),
    },
  ]), [onSelectProject, selectedProjectId])

  const pageColumns = useMemo<TableColumnsType<UiPage>>(() => ([
    {
      title: '页面',
      key: 'page',
      render: (_, record) => (
        <button
          className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
            record.id === selectedPageId
              ? 'border-sky-300 bg-sky-50'
              : 'border-transparent bg-white hover:border-slate-200 hover:bg-slate-50'
          }`}
          type="button"
          onClick={() => onSelectPage(record.id)}
        >
          <div className="font-medium text-slate-900">{record.name}</div>
          <div className="text-xs text-slate-500">{record.routePath || record.code}</div>
        </button>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (value: string) => <Tag color={value === 'published' ? 'green' : 'gold'}>{value}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" onClick={() => openPageModal(record)}>
            编辑
          </Button>
          <Popconfirm title="删除页面？" onConfirm={() => onDeletePage(record.id)}>
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [onDeletePage, onSelectPage, selectedPageId])

  const nodeColumns = useMemo<TableColumnsType<UiPageNode>>(() => ([
    {
      title: '节点',
      key: 'node',
      render: (_, record) => (
        <div>
          <div className="font-medium text-slate-900">{record.nodeName}</div>
          <div className="text-xs text-slate-500">{record.nodeKey}</div>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'nodeType',
      key: 'nodeType',
      width: 100,
      render: (value: string) => <Tag color="blue">{value}</Tag>,
    },
    {
      title: '父节点',
      key: 'parentId',
      width: 140,
      render: (_, record) => (record.parentId ? nodeNameById.get(record.parentId) ?? record.parentId : 'ROOT'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" onClick={() => openNodeModal(record)}>
            编辑
          </Button>
          <Button size="small" onClick={() => openBindingModal(record.id)}>
            绑定字段
          </Button>
          <Popconfirm title="删除节点及其子节点？" onConfirm={() => onDeleteNode(record.id)}>
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [nodeNameById, onDeleteNode])

  const bindingColumns = useMemo<TableColumnsType<UiNodeBinding>>(() => ([
    {
      title: '节点',
      key: 'nodeId',
      width: 160,
      render: (_, record) => nodeNameById.get(record.nodeId) ?? record.nodeId,
    },
    {
      title: '目标属性',
      dataIndex: 'targetProp',
      key: 'targetProp',
      width: 140,
    },
    {
      title: '来源',
      key: 'sourcePath',
      render: (_, record) => (
        <div>
          <div className="text-slate-900">{record.sourcePath || '-'}</div>
          <div className="text-xs text-slate-500">{record.endpointId || '未绑定接口'}</div>
        </div>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 170,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" onClick={() => openBindingModal(record.nodeId, record)}>
            编辑
          </Button>
          <Popconfirm title="删除字段绑定？" onConfirm={() => onDeleteBinding(record.id)}>
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [nodeNameById, onDeleteBinding])

  function openProjectModal(project?: UiProject) {
    setEditingProject(project ?? null)
    setProjectModalOpen(true)
    projectForm.setFieldsValue({
      name: project?.name ?? '',
      code: project?.code ?? '',
      description: project?.description ?? '',
      category: project?.category ?? '',
      status: project?.status ?? 'draft',
      createdBy: project?.createdBy ?? 'ui-builder',
    })
  }

  function openPageModal(page?: UiPage) {
    if (!selectedProjectId && !page?.projectId) {
      return
    }
    setEditingPage(page ?? null)
    setPageModalOpen(true)
    pageForm.setFieldsValue({
      name: page?.name ?? '',
      code: page?.code ?? '',
      title: page?.title ?? '',
      routePath: page?.routePath ?? '',
      rootNodeId: page?.rootNodeId ?? '',
      layoutType: page?.layoutType ?? 'page',
      status: page?.status ?? 'draft',
    })
  }

  function openNodeModal(node?: UiPageNode) {
    if (!selectedPageId) {
      return
    }
    setEditingNode(node ?? null)
    setNodeModalOpen(true)
    nodeForm.resetFields()
    nodeForm.setFieldsValue(node ? {
      parentId: node.parentId ?? undefined,
      nodeKey: node.nodeKey ?? '',
      nodeType: node.nodeType ?? 'Card',
      nodeName: node.nodeName ?? '',
      sortOrder: node.sortOrder ?? 0,
      slotName: node.slotName ?? 'default',
      propsConfig: prettyJson(node.propsConfig ?? '{}'),
      styleConfig: prettyJson(node.styleConfig ?? '{}'),
      status: node.status ?? 'active',
    } : EMPTY_NODE_FORM)
  }

  function openBindingModal(nodeId: string, binding?: UiNodeBinding) {
    setBindingNodeId(nodeId)
    setEditingBinding(binding ?? null)
    setBindingModalOpen(true)
    bindingForm.setFieldsValue({
      endpointId: binding?.endpointId ?? '',
      bindingType: binding?.bindingType ?? 'api',
      targetProp: binding?.targetProp ?? '',
      sourcePath: binding?.sourcePath ?? '$.data',
      transformScript: binding?.transformScript ?? '',
      defaultValue: prettyJson(binding?.defaultValue ?? ''),
      requiredFlag: binding?.requiredFlag ?? false,
    })
  }

  async function submitProject() {
    const values = await projectForm.validateFields()
    await onSaveProject(editingProject?.id, values)
    setProjectModalOpen(false)
  }

  async function submitPage() {
    const values = await pageForm.validateFields()
    if (!selectedProjectId && !editingPage) {
      return
    }
    await onSavePage(selectedProjectId ?? editingPage!.projectId, editingPage?.id, values)
    setPageModalOpen(false)
  }

  async function submitNode() {
    const values = await nodeForm.validateFields()
    if (!selectedPageId) {
      return
    }
    await onSaveNode(selectedPageId, editingNode?.id, values)
    setNodeModalOpen(false)
  }

  async function submitBinding() {
    const values = await bindingForm.validateFields()
    if (!bindingNodeId) {
      return
    }
    await onSaveBinding(bindingNodeId, editingBinding?.id, values)
    setBindingModalOpen(false)
  }

  return (
    <div className="space-y-6">
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={6}>
          <Card
            title="项目"
            className="rounded-[24px]"
            extra={
              <Button type="primary" onClick={() => openProjectModal()}>
                新建项目
              </Button>
            }
          >
            <Table
              rowKey="id"
              loading={loading}
              dataSource={projects}
              columns={projectColumns}
              showHeader={false}
              pagination={{
                current: projectPagination.current,
                pageSize: projectPagination.pageSize,
                total: projectPagination.total,
                showSizeChanger: true,
                onChange: onProjectPageChange,
              }}
              locale={{ emptyText: <Empty description="暂无项目" /> }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={18}>
          <div className="space-y-4">
            <Card
              title="页面列表"
              className="rounded-[24px]"
              extra={
                selectedProject ? (
                  <Space>
                    <Button onClick={() => openProjectModal(selectedProject)}>编辑项目</Button>
                    <Popconfirm title="删除当前项目？" onConfirm={() => onDeleteProject(selectedProject.id)}>
                      <Button danger>删除项目</Button>
                    </Popconfirm>
                    <Button type="primary" onClick={() => openPageModal()}>
                      新建页面
                    </Button>
                  </Space>
                ) : undefined
              }
            >
              {selectedProject ? (
                <>
                  <Descriptions column={{ xs: 1, md: 3 }} size="small" className="mb-4">
                    <Descriptions.Item label="项目编码">{selectedProject.code}</Descriptions.Item>
                    <Descriptions.Item label="分类">{selectedProject.category || '-'}</Descriptions.Item>
                    <Descriptions.Item label="状态">{selectedProject.status || '-'}</Descriptions.Item>
                  </Descriptions>
                  <Table
                    rowKey="id"
                    loading={loading}
                    dataSource={pages}
                    columns={pageColumns}
                    pagination={{
                      current: pagePagination.current,
                      pageSize: pagePagination.pageSize,
                      total: pagePagination.total,
                      showSizeChanger: true,
                      onChange: onPagePageChange,
                    }}
                    locale={{ emptyText: <Empty description="当前项目还没有页面" /> }}
                  />
                </>
              ) : (
                <Empty description="先从左侧选择一个项目" />
              )}
            </Card>

            <Card
              title="页面工作台"
              className="rounded-[24px]"
              extra={
                selectedPage ? (
                  <Space>
                    <Button onClick={() => openPageModal(selectedPage)}>编辑页面</Button>
                    <Button
                      onClick={() => {
                        void onRefreshPreview(selectedPage.id).catch(() => undefined)
                      }}
                    >
                      刷新预览
                    </Button>
                    <Button type="primary" onClick={() => openNodeModal()}>
                      新建节点
                    </Button>
                  </Space>
                ) : undefined
              }
            >
              {selectedPage && pageDetail ? (
                <div className="space-y-4">
                  <Descriptions column={{ xs: 1, md: 4 }} size="small">
                    <Descriptions.Item label="页面编码">{pageDetail.page.code}</Descriptions.Item>
                    <Descriptions.Item label="路由">{pageDetail.page.routePath || '-'}</Descriptions.Item>
                    <Descriptions.Item label="根节点">{pageDetail.page.rootNodeId || '-'}</Descriptions.Item>
                    <Descriptions.Item label="更新时间">{formatDateTime(pageDetail.page.updatedAt)}</Descriptions.Item>
                  </Descriptions>
                  <Alert
                    type="info"
                    showIcon
                    message="页面配置由节点树 + 字段绑定共同组成。建议先创建根 Card，再逐步补 Metric/Table/Chart 等子节点。"
                  />
                  <Row gutter={[16, 16]}>
                    <Col xs={24} xl={14}>
                      <Card
                        size="small"
                        title={`节点 (${nodes.length})`}
                        extra={<Typography.Text type="secondary">按 parentId + sortOrder 组织树结构</Typography.Text>}
                      >
                        <Table
                          rowKey="id"
                          dataSource={nodes}
                          columns={nodeColumns}
                          pagination={{ pageSize: 6 }}
                          locale={{ emptyText: <Empty description="当前页面还没有节点" /> }}
                        />
                      </Card>
                    </Col>
                    <Col xs={24} xl={10}>
                      <Card size="small" title={`字段绑定 (${bindings.length})`}>
                        <Table
                          rowKey="id"
                          dataSource={bindings}
                          columns={bindingColumns}
                          pagination={{ pageSize: 6 }}
                          locale={{ emptyText: <Empty description="当前页面还没有字段绑定" /> }}
                        />
                      </Card>
                    </Col>
                  </Row>
                  {preview?.spec ? (
                    <Card size="small" title="当前预览 Spec">
                      <pre className="max-h-[320px] overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-100">
                        {prettyJson(preview.spec)}
                      </pre>
                    </Card>
                  ) : null}
                </div>
              ) : (
                <Empty description="选择页面后，这里会展示节点树、字段绑定和当前 spec 预览" />
              )}
            </Card>
          </div>
        </Col>
      </Row>

      <Modal
        title={editingProject ? '编辑项目' : '新建项目'}
        open={projectModalOpen}
        onOk={() => {
          void submitProject().catch(() => undefined)
        }}
        onCancel={() => setProjectModalOpen(false)}
        width={720}
        destroyOnHidden
      >
        <Form layout="vertical" form={projectForm}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="code" label="项目编码" rules={[{ required: true, message: '请输入项目编码' }]}>
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="category" label="分类">
                <Input placeholder="dashboard / crm / ops" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="status" label="状态">
                <Select options={statusOptions} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="createdBy" label="创建人">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingPage ? '编辑页面' : '新建页面'}
        open={pageModalOpen}
        onOk={() => {
          void submitPage().catch(() => undefined)
        }}
        onCancel={() => setPageModalOpen(false)}
        width={720}
        destroyOnHidden
      >
        <Form layout="vertical" form={pageForm}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="页面名称" rules={[{ required: true, message: '请输入页面名称' }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="code" label="页面编码" rules={[{ required: true, message: '请输入页面编码' }]}>
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="title" label="展示标题">
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="routePath" label="访问路由">
                <Input placeholder="/workbench/sales-dashboard" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="rootNodeId" label="根节点ID">
                <Input placeholder="留空时自动取首个顶级节点" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="layoutType" label="布局类型">
                <Input placeholder="page" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="status" label="状态">
            <Select options={statusOptions} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingNode ? '编辑节点' : '新建节点'}
        open={nodeModalOpen}
        forceRender
        onOk={() => {
          void submitNode().catch(() => undefined)
        }}
        onCancel={() => setNodeModalOpen(false)}
        width={860}
        destroyOnHidden
      >
        <Form layout="vertical" form={nodeForm}>
          <Form.Item label="当前页面">
            <Input value={selectedPage ? `${selectedPage.name} (${selectedPage.code})` : ''} disabled />
          </Form.Item>
          <Alert
            type="info"
            showIcon
            message="Card 类型适合做容器；Metric、Table、List、Chart 通常作为叶子节点。"
            className="mb-4"
          />
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="nodeName" label="节点名称" rules={[{ required: true, message: '请输入节点名称' }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="nodeKey" label="节点 Key" rules={[{ required: true, message: '请输入节点 Key' }]}>
                <Input placeholder="salesChart" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="nodeType" label="节点类型" rules={[{ required: true }]}>
                <Select options={nodeTypes.map((item) => ({ label: item.type, value: item.type }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="parentId" label="父节点">
                <Select
                  allowClear
                  options={nodes.map((node) => ({ label: `${node.nodeName} (${node.nodeKey})`, value: node.id }))}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="sortOrder" label="排序">
                <InputNumber className="w-full" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="slotName" label="槽位名">
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="propsConfig" label="静态 Props(JSON)">
            <Input.TextArea rows={8} />
          </Form.Item>
          <Form.Item name="styleConfig" label="样式配置(JSON)">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={[{ label: 'active', value: 'active' }, { label: 'inactive', value: 'inactive' }]} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingBinding ? '编辑字段绑定' : '新建字段绑定'}
        open={bindingModalOpen}
        onOk={() => {
          void submitBinding().catch(() => undefined)
        }}
        onCancel={() => setBindingModalOpen(false)}
        width={760}
        destroyOnHidden
      >
        <Form layout="vertical" form={bindingForm}>
          <Form.Item name="bindingType" label="绑定类型" rules={[{ required: true }]}>
            <Select
              options={[
                { label: 'api', value: 'api' },
                { label: 'static', value: 'static' },
                { label: 'expression', value: 'expression' },
                { label: 'mixed', value: 'mixed' },
              ]}
            />
          </Form.Item>
          <Form.Item name="endpointId" label="来源接口">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              options={endpoints.map((endpoint) => ({
                label: `${endpoint.method} ${endpoint.path} | ${endpoint.name}`,
                value: endpoint.id,
              }))}
            />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="targetProp" label="目标属性" rules={[{ required: true, message: '请输入目标属性' }]}>
                <Input placeholder="value / option.series / items" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="sourcePath" label="来源路径(JSONPath)">
                <Input placeholder="$.data.totalRevenue" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="transformScript" label="转换器">
                <Input placeholder="例如：tableRows" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="requiredFlag" label="必填绑定">
                <Select
                  options={[
                    { label: '否', value: false },
                    { label: '是', value: true },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="defaultValue" label="默认值(JSON 或文本)">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            当前支持简单 JSONPath 和内置 `tableRows` 转换器，足够把对象数组转成 Table 所需的二维数组。
          </Typography.Paragraph>
        </Form>
      </Modal>
    </div>
  )
}
