import { useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
} from 'antd'
import type { TableColumnsType } from 'antd'

import { formatDateTime, prettyJson } from '../helpers'
import type {
  SemanticFieldAlias,
  SemanticFieldAliasRequest,
  SemanticFieldDict,
  SemanticFieldDictRequest,
  SemanticFieldValueMap,
  SemanticFieldValueMapRequest,
} from '../types'

const fieldTypeOptions = [
  { label: 'Text', value: 'text' },
  { label: 'Select', value: 'select' },
  { label: 'Date', value: 'date' },
  { label: 'Number', value: 'number' },
]

const activeOptions = [
  { label: '启用', value: 1 },
  { label: '停用', value: 0 },
]

const aliasSourceOptions = [
  { label: '手工维护', value: 'manual' },
  { label: 'AI 推断', value: 'ai' },
]

interface SemanticFieldTabProps {
  semanticFields: SemanticFieldDict[]
  aliases: SemanticFieldAlias[]
  valueMaps: SemanticFieldValueMap[]
  selectedSemanticFieldId?: number
  loading: boolean
  fieldPagination: {
    current: number
    pageSize: number
    total: number
  }
  aliasPagination: {
    current: number
    pageSize: number
    total: number
  }
  valueMapPagination: {
    current: number
    pageSize: number
    total: number
  }
  onSelectSemanticField: (dictId: number) => void
  onFieldPageChange: (page: number, size: number) => void
  onAliasPageChange: (page: number, size: number) => void
  onValueMapPageChange: (page: number, size: number) => void
  onSaveSemanticField: (dictId: number | undefined, payload: SemanticFieldDictRequest) => Promise<void>
  onDeleteSemanticField: (dictId: number) => Promise<void>
  onSaveAlias: (aliasId: number | undefined, payload: SemanticFieldAliasRequest) => Promise<void>
  onDeleteAlias: (aliasId: number) => Promise<void>
  onSaveValueMap: (valueMapId: number | undefined, payload: SemanticFieldValueMapRequest) => Promise<void>
  onDeleteValueMap: (valueMapId: number) => Promise<void>
}

export function SemanticFieldTab({
  semanticFields,
  aliases,
  valueMaps,
  selectedSemanticFieldId,
  loading,
  fieldPagination,
  aliasPagination,
  valueMapPagination,
  onSelectSemanticField,
  onFieldPageChange,
  onAliasPageChange,
  onValueMapPageChange,
  onSaveSemanticField,
  onDeleteSemanticField,
  onSaveAlias,
  onDeleteAlias,
  onSaveValueMap,
  onDeleteValueMap,
}: SemanticFieldTabProps) {
  const [dictModalOpen, setDictModalOpen] = useState(false)
  const [aliasModalOpen, setAliasModalOpen] = useState(false)
  const [valueMapModalOpen, setValueMapModalOpen] = useState(false)
  const [editingDict, setEditingDict] = useState<SemanticFieldDict | null>(null)
  const [editingAlias, setEditingAlias] = useState<SemanticFieldAlias | null>(null)
  const [editingValueMap, setEditingValueMap] = useState<SemanticFieldValueMap | null>(null)
  const [dictForm] = Form.useForm<SemanticFieldDictRequest>()
  const [aliasForm] = Form.useForm<SemanticFieldAliasRequest>()
  const [valueMapForm] = Form.useForm<SemanticFieldValueMapRequest>()

  const selectedDict = useMemo(
    () => semanticFields.find((item) => item.id === selectedSemanticFieldId),
    [semanticFields, selectedSemanticFieldId],
  )

  useEffect(() => {
    if (!semanticFields.length || selectedSemanticFieldId) {
      return
    }
    onSelectSemanticField(semanticFields[0].id)
  }, [onSelectSemanticField, selectedSemanticFieldId, semanticFields])

  const dictColumns = useMemo<TableColumnsType<SemanticFieldDict>>(() => ([
    {
      title: '标准字段',
      key: 'dict',
      render: (_, record) => (
        <button
          className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
            record.id === selectedSemanticFieldId
              ? 'border-sky-300 bg-sky-50'
              : 'border-slate-200 bg-white hover:border-slate-300'
          }`}
          onClick={() => onSelectSemanticField(record.id)}
          type="button"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="font-medium text-slate-900">{record.label}</div>
              <div className="text-xs text-slate-500">{record.standardKey}</div>
            </div>
            <Tag color={record.isActive === 1 ? 'green' : 'default'}>
              {record.isActive === 1 ? '启用' : '停用'}
            </Tag>
          </div>
          <div className="mt-2 text-xs text-slate-500">{record.fieldType}</div>
        </button>
      ),
    },
  ]), [onSelectSemanticField, selectedSemanticFieldId])

  const aliasColumns = useMemo<TableColumnsType<SemanticFieldAlias>>(() => ([
    { title: '原始字段名', dataIndex: 'alias', key: 'alias', width: 180 },
    { title: '接口ID', dataIndex: 'apiId', key: 'apiId' },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (value?: string | null) => value ? <Tag color={value === 'ai' ? 'purple' : 'blue'}>{value}</Tag> : '-',
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 180,
      render: (value?: string | null) => formatDateTime(value),
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" onClick={() => openAliasModal(record)}>
            编辑
          </Button>
          <Popconfirm title="删除这条别名映射？" onConfirm={() => onDeleteAlias(record.id)}>
            <Button danger size="small">
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [onDeleteAlias])

  const valueMapColumns = useMemo<TableColumnsType<SemanticFieldValueMap>>(() => ([
    { title: '标准值', dataIndex: 'standardValue', key: 'standardValue', width: 160 },
    { title: '原始值', dataIndex: 'rawValue', key: 'rawValue', width: 160 },
    {
      title: '接口级覆盖',
      dataIndex: 'apiId',
      key: 'apiId',
      render: (value?: string | null) => value || <Tag color="default">全局</Tag>,
    },
    { title: '排序', dataIndex: 'sortOrder', key: 'sortOrder', width: 90 },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_, record) => (
        <Space size="small">
          <Button size="small" onClick={() => openValueMapModal(record)}>
            编辑
          </Button>
          <Popconfirm title="删除这条值映射？" onConfirm={() => onDeleteValueMap(record.id)}>
            <Button danger size="small">
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]), [onDeleteValueMap])

  function openDictModal(dict?: SemanticFieldDict) {
    setEditingDict(dict ?? null)
    setDictModalOpen(true)
    dictForm.setFieldsValue({
      standardKey: dict?.standardKey ?? '',
      label: dict?.label ?? '',
      fieldType: dict?.fieldType ?? 'text',
      category: dict?.category ?? '',
      valueMap: prettyJson(dict?.valueMap ?? '{}'),
      description: dict?.description ?? '',
      isActive: dict?.isActive ?? 1,
    })
  }

  function openAliasModal(alias?: SemanticFieldAlias) {
    if (!selectedDict) {
      return
    }
    setEditingAlias(alias ?? null)
    setAliasModalOpen(true)
    aliasForm.setFieldsValue({
      standardKey: alias?.standardKey ?? selectedDict.standardKey,
      alias: alias?.alias ?? '',
      apiId: alias?.apiId ?? '',
      source: alias?.source ?? 'manual',
    })
  }

  function openValueMapModal(valueMap?: SemanticFieldValueMap) {
    if (!selectedDict) {
      return
    }
    setEditingValueMap(valueMap ?? null)
    setValueMapModalOpen(true)
    valueMapForm.setFieldsValue({
      standardKey: valueMap?.standardKey ?? selectedDict.standardKey,
      apiId: valueMap?.apiId ?? '',
      standardValue: valueMap?.standardValue ?? '',
      rawValue: valueMap?.rawValue ?? '',
      sortOrder: valueMap?.sortOrder ?? 0,
    })
  }

  async function submitDict() {
    const values = await dictForm.validateFields()
    await onSaveSemanticField(editingDict?.id, values)
    setDictModalOpen(false)
    setEditingDict(null)
    dictForm.resetFields()
  }

  async function submitAlias() {
    const values = await aliasForm.validateFields()
    await onSaveAlias(editingAlias?.id, values)
    setAliasModalOpen(false)
    setEditingAlias(null)
    aliasForm.resetFields()
  }

  async function submitValueMap() {
    const values = await valueMapForm.validateFields()
    await onSaveValueMap(editingValueMap?.id, values)
    setValueMapModalOpen(false)
    setEditingValueMap(null)
    valueMapForm.resetFields()
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <Card
          title="语义字段字典"
          extra={(
            <Button type="primary" onClick={() => openDictModal()}>
              新建字段
            </Button>
          )}
          className="rounded-[24px]"
        >
          <Table
            rowKey="id"
            loading={loading}
            dataSource={semanticFields}
            columns={dictColumns}
            pagination={{
              current: fieldPagination.current,
              pageSize: fieldPagination.pageSize,
              total: fieldPagination.total,
              onChange: onFieldPageChange,
            }}
            locale={{ emptyText: '暂无语义字段字典' }}
          />
        </Card>

        <div className="space-y-5">
          <Card
            className="rounded-[24px]"
            title="字段详情"
            extra={selectedDict ? (
              <Space>
                <Button onClick={() => openDictModal(selectedDict)} size="small">
                  编辑字段
                </Button>
                <Popconfirm title="删除当前语义字段及其下游映射？" onConfirm={() => onDeleteSemanticField(selectedDict.id)}>
                  <Button danger size="small">
                    删除字段
                  </Button>
                </Popconfirm>
              </Space>
            ) : undefined}
          >
            {selectedDict ? (
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="text-xs text-slate-500">标准字段 Key</div>
                  <div className="mt-1 font-medium text-slate-900">{selectedDict.standardKey}</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="text-xs text-slate-500">字段类型</div>
                  <div className="mt-1 font-medium text-slate-900">{selectedDict.fieldType}</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 md:col-span-2">
                  <div className="text-xs text-slate-500">描述</div>
                  <div className="mt-1 whitespace-pre-wrap text-slate-900">{selectedDict.description || '-'}</div>
                </div>
              </div>
            ) : (
              <Empty description="请选择左侧语义字段后查看详情" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>

          <Card
            title="字段别名映射"
            extra={(
              <Button disabled={!selectedDict} onClick={() => openAliasModal()} type="primary">
                新建别名
              </Button>
            )}
            className="rounded-[24px]"
          >
            <Table
              rowKey="id"
              loading={loading}
              dataSource={aliases}
              columns={aliasColumns}
              pagination={{
                current: aliasPagination.current,
                pageSize: aliasPagination.pageSize,
                total: aliasPagination.total,
                onChange: onAliasPageChange,
              }}
              locale={{ emptyText: selectedDict ? '当前标准字段暂无别名映射' : '请选择语义字段后查看' }}
            />
          </Card>

          <Card
            title="字段值映射"
            extra={(
              <Button disabled={!selectedDict} onClick={() => openValueMapModal()} type="primary">
                新建值映射
              </Button>
            )}
            className="rounded-[24px]"
          >
            <Table
              rowKey="id"
              loading={loading}
              dataSource={valueMaps}
              columns={valueMapColumns}
              pagination={{
                current: valueMapPagination.current,
                pageSize: valueMapPagination.pageSize,
                total: valueMapPagination.total,
                onChange: onValueMapPageChange,
              }}
              locale={{ emptyText: selectedDict ? '当前标准字段暂无值映射' : '请选择语义字段后查看' }}
            />
          </Card>
        </div>
      </div>

      <Modal
        destroyOnClose
        open={dictModalOpen}
        title={editingDict ? '编辑语义字段' : '新建语义字段'}
        onCancel={() => setDictModalOpen(false)}
        onOk={() => void submitDict()}
      >
        <Form form={dictForm} layout="vertical">
          <Form.Item label="标准字段 Key" name="standardKey" rules={[{ required: true }]}>
            <Input placeholder="gender" />
          </Form.Item>
          <Form.Item label="展示名" name="label" rules={[{ required: true }]}>
            <Input placeholder="性别" />
          </Form.Item>
          <Form.Item label="字段类型" name="fieldType" rules={[{ required: true }]}>
            <Select options={fieldTypeOptions} />
          </Form.Item>
          <Form.Item label="业务域" name="category">
            <Input placeholder="user/order/product" />
          </Form.Item>
          <Form.Item label="全局值映射(JSON)" name="valueMap">
            <Input.TextArea rows={5} />
          </Form.Item>
          <Form.Item label="字段描述" name="description">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item label="状态" name="isActive">
            <Select options={activeOptions} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        destroyOnClose
        open={aliasModalOpen}
        title={editingAlias ? '编辑字段别名' : '新建字段别名'}
        onCancel={() => setAliasModalOpen(false)}
        onOk={() => void submitAlias()}
      >
        <Form form={aliasForm} layout="vertical">
          <Form.Item label="标准字段 Key" name="standardKey">
            <Input disabled />
          </Form.Item>
          <Form.Item label="原始字段名" name="alias" rules={[{ required: true }]}>
            <Input placeholder="sex / userSex" />
          </Form.Item>
          <Form.Item label="接口 ID" name="apiId" rules={[{ required: true }]}>
            <Input placeholder="填写 UiApiEndpoint.id" />
          </Form.Item>
          <Form.Item label="来源" name="source">
            <Select options={aliasSourceOptions} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        destroyOnClose
        open={valueMapModalOpen}
        title={editingValueMap ? '编辑字段值映射' : '新建字段值映射'}
        onCancel={() => setValueMapModalOpen(false)}
        onOk={() => void submitValueMap()}
      >
        <Form form={valueMapForm} layout="vertical">
          <Form.Item label="标准字段 Key" name="standardKey">
            <Input disabled />
          </Form.Item>
          <Form.Item label="接口 ID" name="apiId" extra="留空表示全局值映射，有值表示接口级覆盖。">
            <Input placeholder="可选，填写 UiApiEndpoint.id" />
          </Form.Item>
          <Form.Item label="标准值" name="standardValue" rules={[{ required: true }]}>
            <Input placeholder="男" />
          </Form.Item>
          <Form.Item label="原始值" name="rawValue" rules={[{ required: true }]}>
            <Input placeholder="1 / M / male" />
          </Form.Item>
          <Form.Item label="排序" name="sortOrder">
            <InputNumber className="w-full" min={0} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
