import { useEffect, useState } from 'react'
import { Modal, Table, Spin } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { theme } from '../../styles/theme'

interface DrillDownModalProps<T> {
  open: boolean
  title: string
  onClose: () => void
  fetchData: () => Promise<T[]>
  columns: ColumnsType<T>
  rowKey: string | ((record: T) => string)
}

function DrillDownModal<T extends object>({ open, title, onClose, fetchData, columns, rowKey }: DrillDownModalProps<T>) {
  const [data, setData] = useState<T[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return undefined

    let cancelled = false

    const loadData = async () => {
      setLoading(true)

      try {
        const nextData = await fetchData()
        if (!cancelled) {
          setData(nextData)
        }
      } catch {
        if (!cancelled) {
          setData([])
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadData()

    return () => {
      cancelled = true
    }
  }, [open, fetchData])

  return (
    <Modal
      open={open}
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 3,
            height: 16,
            borderRadius: 2,
            background: `linear-gradient(180deg, ${theme.colors.accentCyan}, ${theme.colors.accentCyan}50)`,
            boxShadow: `0 0 6px ${theme.colors.accentCyan}40`,
          }} />
          <span style={{ color: theme.colors.textPrimary, fontSize: 15, fontWeight: 600 }}>{title}</span>
        </div>
      }
      onCancel={onClose}
      footer={null}
      width={960}
      destroyOnClose
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
      ) : (
        <Table<T>
          columns={columns}
          dataSource={data}
          rowKey={rowKey}
          size="small"
          pagination={{ pageSize: 10, showSizeChanger: false, showTotal: (t) => `共 ${t} 条` }}
          scroll={{ x: 'max-content' }}
        />
      )}
    </Modal>
  )
}

export default DrillDownModal
