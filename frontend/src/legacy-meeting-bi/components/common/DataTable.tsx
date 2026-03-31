import { Table, type TableProps } from 'antd'

function DataTable<T extends object>(props: TableProps<T>) {
  return (
    <Table<T>
      size="small"
      pagination={{ pageSize: 15, showSizeChanger: false }}
      scroll={{ x: 'max-content' }}
      {...props}
    />
  )
}

export default DataTable
