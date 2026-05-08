import { Card, Col, Row, Space, Steps, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { useMemo } from 'react'

import type { UiBuilderOverview, UiBuilderTableSchema } from '../types'

const stepItems = [
  { title: '接口导入' },
  { title: '接口联调' },
  { title: '页面编排' },
  { title: '字段绑定' },
  { title: 'Spec 发布' },
]

interface OverviewTabProps {
  overview: UiBuilderOverview
}

export function OverviewTab({ overview }: OverviewTabProps) {
  const tableColumns = useMemo<TableColumnsType<UiBuilderTableSchema>>(() => ([
    {
      title: '表名',
      dataIndex: 'name',
      key: 'name',
      width: 220,
    },
    {
      title: '用途',
      dataIndex: 'purpose',
      key: 'purpose',
    },
    {
      title: '关键字段',
      key: 'fields',
      render: (_, record) => (
        <Space wrap>
          {record.fields.map((field) => (
            <Tag key={`${record.name}-${field.name}`} color="blue">
              {field.name}
            </Tag>
          ))}
        </Space>
      ),
    },
  ]), [])

  return (
    <div className="space-y-6">
      <section className="rounded-[28px] border border-slate-200/80 bg-white px-8 py-8 shadow-sm">
        <Space direction="vertical" size={12}>
          <Typography.Text type="secondary">配置中心 / JSON Render</Typography.Text>
          <Typography.Title level={2} style={{ margin: 0 }}>
            {overview.moduleName}
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0, maxWidth: 900 }}>
            {overview.description}
          </Typography.Paragraph>
        </Space>
      </section>

      <Card title="落地流程" className="rounded-[24px]">
        <Steps current={-1} items={stepItems} />
        <div className="mt-6 grid gap-3">
          {overview.workflowSteps.map((step) => (
            <div key={step} className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
              {step}
            </div>
          ))}
        </div>
      </Card>

      <Row gutter={[16, 16]}>
        {overview.features.map((feature) => (
          <Col xs={24} md={12} xl={8} key={feature.title}>
            <Card title={feature.title} className="h-full rounded-[24px]">
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                {feature.description}
              </Typography.Paragraph>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card title="页面节点类型" className="rounded-[24px]">
            <div className="grid gap-4">
              {overview.nodeTypes.map((nodeType) => (
                <div key={nodeType.type} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <Typography.Title level={5} style={{ margin: 0 }}>
                      {nodeType.type}
                    </Typography.Title>
                    <Tag color={nodeType.supportsChildren ? 'green' : 'default'}>
                      {nodeType.supportsChildren ? '可承载子节点' : '叶子节点'}
                    </Tag>
                  </div>
                  <Typography.Paragraph type="secondary" className="mt-2" style={{ marginBottom: 12 }}>
                    {nodeType.description}
                  </Typography.Paragraph>
                  <Space wrap>
                    {nodeType.keyProps.map((prop) => (
                      <Tag key={`${nodeType.type}-${prop}`} color="processing">
                        {prop}
                      </Tag>
                    ))}
                  </Space>
                </div>
              ))}
            </div>
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="接口认证方式" className="rounded-[24px]">
            <div className="grid gap-3">
              {overview.authTypes.map((authType) => (
                <div key={authType.type} className="rounded-2xl border border-slate-200 px-4 py-3">
                  <div className="flex items-center justify-between gap-4">
                    <Typography.Text strong>{authType.type}</Typography.Text>
                    <Tag color="purple">{authType.description}</Tag>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="后端表结构设计" className="rounded-[24px]">
        <Table
          rowKey="name"
          columns={tableColumns}
          dataSource={overview.tables}
          pagination={false}
          expandable={{
            expandedRowRender: (record) => (
              <Table
                rowKey="name"
                pagination={false}
                size="small"
                columns={[
                  { title: '字段', dataIndex: 'name', key: 'name', width: 220 },
                  { title: '类型', dataIndex: 'type', key: 'type', width: 160 },
                  { title: '说明', dataIndex: 'description', key: 'description' },
                ]}
                dataSource={record.fields}
              />
            ),
          }}
        />
      </Card>
    </div>
  )
}
