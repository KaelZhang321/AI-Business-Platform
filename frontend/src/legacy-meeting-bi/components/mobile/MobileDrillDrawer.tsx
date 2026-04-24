import { useEffect, useState } from 'react'
import { Drawer, Table, Spin } from 'antd'
import type { ColumnsType } from 'antd/es/table'

interface MobileDrillDrawerProps<T> {
  open: boolean
  title: string
  onClose: () => void
  fetchData: () => Promise<T[]>
  columns: ColumnsType<T>
  rowKey: string | ((record: T) => string)
}

function MobileDrillDrawer<T extends object>({ open, title, onClose, fetchData, columns, rowKey }: MobileDrillDrawerProps<T>) {
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
    <Drawer
      open={open}
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 3,
            height: 16,
            borderRadius: 2,
            background: '#3B82F6',
          }} />
          <span style={{ color: '#1A1D2E', fontSize: 15, fontWeight: 600 }}>{title}</span>
        </div>
      }
      placement="bottom"
      height="75vh"
      onClose={onClose}
      destroyOnClose
      styles={{
        header: {
          background: '#FFFFFF',
          borderBottom: '1px solid #F3F4F6',
          padding: '14px 16px',
        },
        body: {
          background: '#FFFFFF',
          padding: '12px 8px',
        },
      }}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
      ) : (
        <div className="mobile-table-scroll" style={{ margin: 0, padding: 0 }}>
          <Table<T>
            columns={columns}
            dataSource={data}
            rowKey={rowKey}
            size="small"
            pagination={{ pageSize: 8, simple: true, showSizeChanger: false, showTotal: (t) => `共 ${t} 条` }}
            scroll={{ x: 'max-content' }}
          />
        </div>
      )}
    </Drawer>
  )
}

export default MobileDrillDrawer
