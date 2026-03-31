import React, { useMemo, useState, useCallback } from 'react'
import { useRegistrationChart, useRegistrationMatrix } from '../../hooks/useApi'
import DashboardCard from '../common/DashboardCard'
import SectionTitle from '../common/SectionTitle'
import LoadingSkeleton from '../common/LoadingSkeleton'
import StackedBarChart from '../charts/StackedBarChart'
import DataTable from '../common/DataTable'
import DrillDownModal from '../common/DrillDownModal'
import { fetchRegistrationDetail, type RegistrationDetail } from '../../api/registration'
import type { MatrixRow } from '../../api/registration'
import { theme } from '../../styles/theme'

const columns = [
  { title: '大区', dataIndex: 'region', key: 'region', fixed: 'left' as const, width: 72 },
  { title: '千万(报)', dataIndex: 'qianwan_register', key: 'qr', width: 68 },
  { title: '千万(到)', dataIndex: 'qianwan_arrive', key: 'qa', width: 68, render: (v: number) => <span style={{ color: v > 0 ? theme.colors.accentGreen : theme.colors.textSecondary, fontWeight: v > 0 ? 600 : 400 }}>{v}</span> },
  { title: '百万(报)', dataIndex: 'baiwan_register', key: 'br', width: 68 },
  { title: '百万(到)', dataIndex: 'baiwan_arrive', key: 'ba', width: 68, render: (v: number) => <span style={{ color: v > 0 ? theme.colors.accentGreen : theme.colors.textSecondary, fontWeight: v > 0 ? 600 : 400 }}>{v}</span> },
  { title: '普通(报)', dataIndex: 'putong_register', key: 'pr', width: 68 },
  { title: '普通(到)', dataIndex: 'putong_arrive', key: 'pa', width: 68, render: (v: number) => <span style={{ color: v > 0 ? theme.colors.accentGreen : theme.colors.textSecondary, fontWeight: v > 0 ? 600 : 400 }}>{v}</span> },
  { title: '总报名', dataIndex: 'total_register', key: 'tr', width: 62, render: (v: number) => <strong style={{ color: theme.colors.accentCyan }}>{v}</strong> },
  { title: '总抵达', dataIndex: 'total_arrive', key: 'ta', width: 62, render: (v: number) => <strong style={{ color: theme.colors.accentGreen }}>{v}</strong> },
]

const detailColumns = [
  { title: '客户姓名', dataIndex: 'customer_name', key: 'name' },
  { title: '签到状态', dataIndex: 'sign_in_status', key: 'status', render: (v: string) => <span style={{ color: v === '已签到' ? theme.colors.accentGreen : theme.colors.textSecondary }}>{v || '-'}</span> },
  { title: '客户类别', dataIndex: 'customer_category', key: 'category' },
  { title: '身份类型', dataIndex: 'real_identity', key: 'identity', render: (v: string | null) => v || '未分类' },
  { title: '参会角色', dataIndex: 'attendee_role', key: 'role' },
  { title: '店铺来源', dataIndex: 'store_name', key: 'store' },
]

const RegistrationSection: React.FC = () => {
  const { data: chartData, isLoading: chartLoading } = useRegistrationChart()
  const { data: matrixData, isLoading: matrixLoading } = useRegistrationMatrix()
  const [drillOpen, setDrillOpen] = useState(false)
  const [drillRegion, setDrillRegion] = useState<string>()
  const [drillLevel, setDrillLevel] = useState<string>()

  const { categories, series } = useMemo(() => {
    if (!chartData) return { categories: [], series: [] }
    const regionSet = [...new Set(chartData.map((d) => d.region))]
    const levelSet = [...new Set(chartData.map((d) => d.real_identity || '未分类'))]
    const registerSeries = levelSet.map((level) => ({
      name: `${level}(报名)`,
      stack: 'register',
      data: regionSet.map((region) => chartData.find((d) => d.region === region && (d.real_identity || '未分类') === level)?.register_count || 0),
    }))
    const arriveSeries = levelSet.map((level) => ({
      name: `${level}(抵达)`,
      stack: 'arrive',
      data: regionSet.map((region) => chartData.find((d) => d.region === region && (d.real_identity || '未分类') === level)?.arrive_count || 0),
    }))
    return { categories: regionSet, series: [...registerSeries, ...arriveSeries] }
  }, [chartData])

  const handleChartClick = useCallback((params: { name?: string; seriesName?: string }) => {
    if (params.name && params.seriesName) {
      setDrillRegion(params.name)
      setDrillLevel(params.seriesName.replace(/\((报名|抵达)\)$/, ''))
      setDrillOpen(true)
    }
  }, [])

  const fetchDetail = useCallback(
    () => fetchRegistrationDetail(drillRegion, drillLevel === '未分类' ? '未分类' : drillLevel),
    [drillRegion, drillLevel],
  )

  if (chartLoading) return <LoadingSkeleton />

  return (
    <div>
      <SectionTitle title="报名 VS 签到情况" subtitle="各区域按金额等级的报名与抵达对比" accentColor={theme.colors.accentCyan} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <DashboardCard title="报名/抵达统计" subtitle="按大区·金额等级 | 点击柱体查看明细" fill style={{ minHeight: 420 }}>
          <StackedBarChart categories={categories} series={series} height="100%" onBarClick={handleChartClick} />
        </DashboardCard>
        <DashboardCard title="金额等级矩阵" subtitle="各大区报名与抵达明细">
          {matrixLoading ? <LoadingSkeleton /> : <DataTable<MatrixRow> columns={columns} dataSource={matrixData || []} rowKey="region" />}
        </DashboardCard>
      </div>
      <DrillDownModal<RegistrationDetail>
        open={drillOpen}
        title={`客户明细 — ${drillRegion || ''} · ${drillLevel || ''}`}
        onClose={() => setDrillOpen(false)}
        fetchData={fetchDetail}
        columns={detailColumns}
        rowKey={(r) => `${r.customer_name}-${r.store_name}`}
      />
    </div>
  )
}

export default RegistrationSection
