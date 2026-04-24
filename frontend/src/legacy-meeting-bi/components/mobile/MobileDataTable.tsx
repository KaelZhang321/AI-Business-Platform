import { Table, type TableProps } from 'antd'

function MobileDataTable<T extends object>(props: TableProps<T>) {
  return (
    <div className="mobile-table-scroll">
      <Table<T>
        size="small"
        pagination={{ pageSize: 8, simple: true, showSizeChanger: false }}
        scroll={{ x: 'max-content' }}
        {...props}
      />
    </div>
  )
}

export default MobileDataTable
