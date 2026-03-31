import React, { useMemo, useState, useCallback } from 'react'
import { useAchievementChart, useAchievementTable } from '../../../hooks/useApi'
import MobileCard from '../MobileCard'
import MobileDataTable from '../MobileDataTable'
import MobileDrillDrawer from '../MobileDrillDrawer'
import LoadingSkeleton from '../../common/LoadingSkeleton'
import GroupedBarChart from '../../charts/GroupedBarChart'
import { fetchAchievementDetail, type AchievementDetail } from '../../../api/achievement'
import type { AchievementRow } from '../../../api/achievement'

const mono = "'JetBrains Mono', monospace"
const toNum = (v: unknown) => {
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0
  if (typeof v === 'string') {
    const n = Number(v.replace(/,/g, '').trim())
    return Number.isFinite(n) ? n : 0
  }
  return 0
}

const tableColumns = [
  { title: '#', dataIndex: 'row_num', key: 'n', width: 36 },
  { title: '区域', dataIndex: 'region', key: 'r', fixed: 'left' as const, width: 60 },
  { title: '达成(万)', dataIndex: 'actual_amount', key: 'a', width: 80, render: (v: number) => <span style={{ color: '#3B82F6', fontWeight: 600, fontFamily: mono, fontSize: 12 }}>¥{v.toLocaleString()}</span> },
  { title: '目标(万)', dataIndex: 'target_amount', key: 't', width: 80, render: (v: number) => <span style={{ fontFamily: mono, fontSize: 12 }}>¥{v.toLocaleString()}</span> },
  { title: '达成率', dataIndex: 'achievement_rate', key: 'rt', width: 60, render: (v: number | null) => v !== null ? <span style={{ color: v >= 100 ? '#10B981' : '#EF4444', fontWeight: 600, fontFamily: mono, fontSize: 12 }}>{v}%</span> : '-' },
  { title: '差值(万)', dataIndex: 'difference', key: 'd', width: 80, render: (v: number) => <span style={{ color: v >= 0 ? '#10B981' : '#EF4444', fontWeight: 600, fontFamily: mono, fontSize: 12 }}>{v >= 0 ? '+' : ''}{v.toLocaleString()}</span> },
]

const detailColumns = [
  { title: '客户姓名', dataIndex: 'customer_name', key: 'name', width: 80 },
  { title: '区域', dataIndex: 'region', key: 'region', width: 60 },
  { title: '分公司', dataIndex: 'branch', key: 'branch', width: 70 },
  { title: '成交类型', dataIndex: 'deal_type', key: 'type', width: 70 },
  { title: '成交内容', dataIndex: 'deal_content', key: 'content', width: 100 },
  { title: '新成交金额(万)', dataIndex: 'new_deal_amount', key: 'amount', width: 90, render: (v: number) => <span style={{ color: '#3B82F6', fontWeight: 600, fontFamily: mono }}>¥{v.toLocaleString()}</span> },
  { title: '收款金额(万)', dataIndex: 'received_amount', key: 'received', width: 90, render: (v: number) => <span style={{ fontFamily: mono }}>¥{v.toLocaleString()}</span> },
  { title: '方案类型', dataIndex: 'plan_type', key: 'plan', width: 70 },
  { title: '日期', dataIndex: 'record_date', key: 'date', width: 80 },
]

const MobileAchievementSection: React.FC = () => {
  const { data: chartData, isLoading: chartLoading } = useAchievementChart()
  const { data: tableData, isLoading: tableLoading } = useAchievementTable()
  const [drillOpen, setDrillOpen] = useState(false)
  const [drillRegion, setDrillRegion] = useState<string>()

  const chart = useMemo(() => {
    if (!chartData) return { categories: [], series: [] }
    const sortedData = [...chartData].sort((a, b) => toNum(b.deal_amount) - toNum(a.deal_amount))
    return {
      categories: sortedData.map((d) => d.region),
      series: [
        { name: '达成金额', data: sortedData.map((d) => toNum(d.deal_amount)) },
        { name: '成交低限', data: sortedData.map((d) => toNum(d.low_limit)) },
        { name: '成交高限', data: sortedData.map((d) => toNum(d.high_limit)) },
      ],
    }
  }, [chartData])

  const handleChartClick = useCallback((params: { name?: string }) => {
    if (params.name) {
      setDrillRegion(params.name)
      setDrillOpen(true)
    }
  }, [])

  const fetchDetail = useCallback(
    () => fetchAchievementDetail(drillRegion),
    [drillRegion],
  )

  if (chartLoading) return <LoadingSkeleton />

  return (
    <div>
      <MobileCard
        glowColor="#10B981"
        title="目标 VS 达成"
        subtitle="各区域成交目标完成情况"
      >
        <GroupedBarChart categories={chart.categories} series={chart.series} height={260} onBarClick={handleChartClick} />
      </MobileCard>
      <div style={{ height: 12 }} />
      <MobileCard glowColor="#EF4444" title="达成率明细表">
        {tableLoading ? <LoadingSkeleton /> : <MobileDataTable<AchievementRow> columns={tableColumns} dataSource={tableData || []} rowKey="row_num" />}
      </MobileCard>
      <MobileDrillDrawer<AchievementDetail>
        open={drillOpen}
        title={`成交明细 — ${drillRegion || ''}`}
        onClose={() => setDrillOpen(false)}
        fetchData={fetchDetail}
        columns={detailColumns}
        rowKey={(r) => `${r.customer_name}-${r.record_date}`}
      />
    </div>
  )
}

export default MobileAchievementSection
