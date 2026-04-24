import React, { useMemo, useState, useCallback } from 'react'
import { useSourceDistribution, useTargetArrival } from '../../hooks/useApi'
import DashboardCard from '../common/DashboardCard'
import SectionTitle from '../common/SectionTitle'
import LoadingSkeleton from '../common/LoadingSkeleton'
import StackedBarChart from '../charts/StackedBarChart'
import GroupedBarChart from '../charts/GroupedBarChart'
import DrillDownModal from '../common/DrillDownModal'
import { fetchTargetCustomerDetail, type TargetCustomerDetail } from '../../api/source'
import { theme } from '../../styles/theme'

const detailColumns = [
  { title: '客户姓名', dataIndex: 'customer_name', key: 'name' },
  { title: '区域', dataIndex: 'region', key: 'region' },
  { title: '客户等级', dataIndex: 'customer_level', key: 'level' },
  { title: '新老客户', dataIndex: 'new_or_old_customer', key: 'newold' },
  { title: '成交低限', dataIndex: 'min_deal', key: 'min', render: (v: number | null) => v != null ? `¥${v.toLocaleString()}` : '-' },
  { title: '成交高限', dataIndex: 'max_deal', key: 'max', render: (v: number | null) => v != null ? `¥${v.toLocaleString()}` : '-' },
  { title: '铺垫成熟度', dataIndex: 'prep_maturity', key: 'prep' },
  { title: '是否抵达', dataIndex: 'is_arrived', key: 'arrived', render: (v: boolean) => <span style={{ color: v ? theme.colors.accentGreen : theme.colors.accentRed, fontWeight: 600 }}>{v ? '已抵达' : '未抵达'}</span> },
]

const CustomerSourceSection: React.FC = () => {
  const { data: sourceData, isLoading: srcLoading } = useSourceDistribution()
  const { data: targetData, isLoading: tgtLoading } = useTargetArrival()
  const [drillOpen, setDrillOpen] = useState(false)
  const [drillRegion, setDrillRegion] = useState<string>()

  const sourceChart = useMemo(() => {
    if (!sourceData) return { categories: [], series: [] }
    const regions = [...new Set(sourceData.map((d) => d.region))]
    const types = [...new Set(sourceData.map((d) => d.source_type))]
    const series = types.map((t) => ({
      name: t,
      data: regions.map((r) => sourceData.find((d) => d.region === r && d.source_type === t)?.customer_count || 0),
    }))
    return { categories: regions, series }
  }, [sourceData])

  const targetChart = useMemo(() => {
    if (!targetData) return { categories: [], series: [] }
    const regions = targetData.map((d) => d.region)
    return {
      categories: regions,
      series: [
        { name: '目标客户', data: targetData.map((d) => d.target_count) },
        { name: '已抵达', data: targetData.map((d) => d.arrive_count) },
      ],
    }
  }, [targetData])

  const handleTargetClick = useCallback((params: { name?: string }) => {
    if (params.name) {
      setDrillRegion(params.name)
      setDrillOpen(true)
    }
  }, [])

  const fetchDetail = useCallback(
    () => fetchTargetCustomerDetail(drillRegion),
    [drillRegion],
  )

  if (srcLoading) return <LoadingSkeleton />

  return (
    <div>
      <SectionTitle title="客户来源 + 任务进展" subtitle="按大区·来源维度分析客户报名渠道与目标客户抵达" accentColor={theme.colors.accentGreen} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <DashboardCard glowColor={theme.colors.accentCyan} title="客户报名统计" subtitle="按大区·来源类型">
          <StackedBarChart categories={sourceChart.categories} series={sourceChart.series} />
        </DashboardCard>
        <DashboardCard glowColor={theme.colors.accentGreen} title="优质目标客户抵达" subtitle="目标 vs 实际抵达 | 点击柱体查看明细">
          {tgtLoading ? <LoadingSkeleton /> : <GroupedBarChart categories={targetChart.categories} series={targetChart.series} onBarClick={handleTargetClick} />}
        </DashboardCard>
      </div>
      <DrillDownModal<TargetCustomerDetail>
        open={drillOpen}
        title={`目标客户明细 — ${drillRegion || ''}`}
        onClose={() => setDrillOpen(false)}
        fetchData={fetchDetail}
        columns={detailColumns}
        rowKey={(r) => `${r.customer_name}-${r.region}`}
      />
    </div>
  )
}

export default CustomerSourceSection
