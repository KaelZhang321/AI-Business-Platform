import { Alert, Button, Card, Col, Descriptions, Empty, Row, Space, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { useMemo } from 'react'

import { formatDateTime, prettyJson, summarizeSpec } from '../helpers'
import type { UiPage, UiPagePreviewResponse, UiSpecVersion } from '../types'

interface ReleaseTabProps {
  selectedPage?: UiPage
  preview?: UiPagePreviewResponse | null
  versions: UiSpecVersion[]
  loading: boolean
  versionPagination: {
    current: number
    pageSize: number
    total: number
  }
  onVersionPageChange: (page: number, size: number) => void
  onRefreshPreview: (pageId: string) => Promise<void>
  onPublishPage: (pageId: string) => Promise<void>
}

export function ReleaseTab({
  selectedPage,
  preview,
  versions,
  loading,
  versionPagination,
  onVersionPageChange,
  onRefreshPreview,
  onPublishPage,
}: ReleaseTabProps) {
  const summary = summarizeSpec(preview?.spec)

  const versionColumns = useMemo<TableColumnsType<UiSpecVersion>>(() => ([
    {
      title: '版本',
      dataIndex: 'versionNo',
      key: 'versionNo',
      width: 90,
      render: (value: number) => <Tag color="blue">v{value}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'publishStatus',
      key: 'publishStatus',
      width: 120,
      render: (value: string) => <Tag color={value === 'published' ? 'green' : 'default'}>{value}</Tag>,
    },
    {
      title: '发布人',
      dataIndex: 'publishedBy',
      key: 'publishedBy',
      width: 120,
      render: (value?: string | null) => value || '-',
    },
    {
      title: '发布时间',
      dataIndex: 'publishedAt',
      key: 'publishedAt',
      width: 180,
      render: (value?: string | null) => formatDateTime(value),
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 180,
      render: (value?: string | null) => formatDateTime(value),
    },
  ]), [])

  if (!selectedPage) {
    return (
      <Card className="rounded-[24px]">
        <Empty description="先在页面工作台里选择一个页面，才能查看预览和版本发布。" />
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <Card
        title="发布控制台"
        className="rounded-[24px]"
        extra={(
          <Space>
            <Button
              onClick={() => {
                void onRefreshPreview(selectedPage.id).catch(() => undefined)
              }}
            >
              刷新预览
            </Button>
            <Button
              type="primary"
              onClick={() => {
                void onPublishPage(selectedPage.id).catch(() => undefined)
              }}
            >
              发布新版本
            </Button>
          </Space>
        )}
      >
        <Descriptions column={{ xs: 1, md: 4 }} size="small">
          <Descriptions.Item label="页面名称">{selectedPage.name}</Descriptions.Item>
          <Descriptions.Item label="页面编码">{selectedPage.code}</Descriptions.Item>
          <Descriptions.Item label="根节点">{summary.root}</Descriptions.Item>
          <Descriptions.Item label="元素数">{summary.elementCount}</Descriptions.Item>
        </Descriptions>
        <Alert
          className="mt-4"
          type="info"
          showIcon
          message="发布时会基于当前节点树、绑定关系和样例响应生成一份冻结版 json-render spec。"
        />
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={14}>
          <Card title="当前 Spec 预览" className="rounded-[24px]">
            {preview?.spec ? (
              <pre className="max-h-[640px] overflow-auto rounded-2xl bg-slate-950 p-4 text-xs text-slate-100">
                {prettyJson(preview.spec)}
              </pre>
            ) : (
              <Empty description="先点击“刷新预览”生成当前 Spec" />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card title="版本记录" className="rounded-[24px]">
            <Table
              rowKey="id"
              loading={loading}
              dataSource={versions}
              columns={versionColumns}
              pagination={{
                current: versionPagination.current,
                pageSize: versionPagination.pageSize,
                total: versionPagination.total,
                showSizeChanger: true,
                onChange: onVersionPageChange,
              }}
              locale={{ emptyText: <Empty description="还没有发布记录" /> }}
            />
            <Typography.Paragraph type="secondary" className="mt-4" style={{ marginBottom: 0 }}>
              如果你后面要接“回滚版本”或“按版本渲染”，直接读取这里的 `specContent` 即可。
            </Typography.Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
