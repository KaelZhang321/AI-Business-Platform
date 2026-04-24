import React, { useMemo, useState, useCallback } from 'react'
import { useRegistrationMatrix } from '../../../hooks/useApi'
import MobileCard from '../MobileCard'
import MobileDataTable from '../MobileDataTable'
import MobileDrillDrawer from '../MobileDrillDrawer'
import LoadingSkeleton from '../../common/LoadingSkeleton'
import GroupedBarChart from '../../charts/GroupedBarChart'
import { fetchRegistrationDetail, type RegistrationDetail } from '../../../api/registration'
import type { MatrixRow } from '../../../api/registration'


const columns = [
  { title: '大区', dataIndex: 'region', key: 'region', fixed: 'left' as const, width: 60 },
  { title: '千万(报)', dataIndex: 'qianwan_register', key: 'qr', width: 62 },
  { title: '千万(到)', dataIndex: 'qianwan_arrive', key: 'qa', width: 62, render: (v: number) => <span style={{ color: v > 0 ? '#10B981' : '#9CA3AF', fontWeight: v > 0 ? 600 : 400 }}>{v}</span> },
  { title: '百万(报)', dataIndex: 'baiwan_register', key: 'br', width: 62 },
  { title: '百万(到)', dataIndex: 'baiwan_arrive', key: 'ba', width: 62, render: (v: number) => <span style={{ color: v > 0 ? '#10B981' : '#9CA3AF', fontWeight: v > 0 ? 600 : 400 }}>{v}</span> },
  { title: '普通(报)', dataIndex: 'putong_register', key: 'pr', width: 62 },
  { title: '普通(到)', dataIndex: 'putong_arrive', key: 'pa', width: 62, render: (v: number) => <span style={{ color: v > 0 ? '#10B981' : '#9CA3AF', fontWeight: v > 0 ? 600 : 400 }}>{v}</span> },
  { title: '总报名', dataIndex: 'total_register', key: 'tr', width: 56, render: (v: number) => <strong style={{ color: '#3B82F6' }}>{v}</strong> },
  { title: '总抵达', dataIndex: 'total_arrive', key: 'ta', width: 56, render: (v: number) => <strong style={{ color: '#10B981' }}>{v}</strong> },
]

const detailColumns = [
  { title: '客户姓名', dataIndex: 'customer_name', key: 'name', width: 80 },
  { title: '签到状态', dataIndex: 'sign_in_status', key: 'status', width: 70, render: (v: string) => <span style={{ color: v === '已签到' ? '#10B981' : '#9CA3AF' }}>{v || '-'}</span> },
  { title: '客户类别', dataIndex: 'customer_category', key: 'category', width: 70 },
  { title: '身份类型', dataIndex: 'real_identity', key: 'identity', width: 70, render: (v: string | null) => v || '未分类' },
  { title: '参会角色', dataIndex: 'attendee_role', key: 'role', width: 70 },
  { title: '店铺来源', dataIndex: 'store_name', key: 'store', width: 80 },
]

const MobileRegistrationSection: React.FC = () => {
  const { data: matrixData, isLoading: matrixLoading } = useRegistrationMatrix()
  const [drillOpen, setDrillOpen] = useState(false)
  const [drillRegion, setDrillRegion] = useState<string>()

  const { categories, series } = useMemo(() => {
    if (!matrixData || matrixData.length === 0) return { categories: [], series: [] as { name: string; data: number[] }[] }
    return {
      categories: matrixData.map((item) => item.region),
      series: [
        { name: '报名人数', data: matrixData.map((item) => item.total_register) },
        { name: '抵达人数', data: matrixData.map((item) => item.total_arrive) },
      ],
    }
  }, [matrixData])

  const handleChartClick = useCallback((params: { name?: string }) => {
    if (params.name) {
      setDrillRegion(params.name)
      setDrillOpen(true)
    }
  }, [])

  const fetchDetail = useCallback(
    () => fetchRegistrationDetail(drillRegion),
    [drillRegion],
  )

  if (matrixLoading) return <LoadingSkeleton />

  return (
    <div>
      <MobileCard title="报名/抵达统计" subtitle="按区域查看报名与抵达人数对比" glowColor="#3B82F6">
        <GroupedBarChart categories={categories} series={series} height={260} onBarClick={handleChartClick} />
      </MobileCard>
      <div style={{ height: 12 }} />
      <MobileCard title="金额等级矩阵" glowColor="#3B82F6">
        {matrixLoading ? <LoadingSkeleton /> : <MobileDataTable<MatrixRow> columns={columns} dataSource={matrixData || []} rowKey="region" />}
      </MobileCard>
      <MobileDrillDrawer<RegistrationDetail>
        open={drillOpen}
        title={`客户明细 — ${drillRegion || ''}`}
        onClose={() => setDrillOpen(false)}
        fetchData={fetchDetail}
        columns={detailColumns}
        rowKey={(r) => `${r.customer_name}-${r.store_name}`}
      />
    </div>
  )
}

export default MobileRegistrationSection
