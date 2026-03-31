import React, { useMemo, useState } from 'react'
import { DatePicker, Select } from 'antd'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import { useOperationsKpi, useTrendData } from '../../hooks/useApi'
import DashboardCard from '../common/DashboardCard'
import SectionTitle from '../common/SectionTitle'
import LoadingSkeleton from '../common/LoadingSkeleton'
import KpiCard from '../common/KpiCard'
import MultiLineChart from '../charts/MultiLineChart'
import { theme } from '../../styles/theme'

const OperationsSection: React.FC = () => {
  const [selectedDate, setSelectedDate] = useState<string>(dayjs().format('YYYY-MM-DD'))
  const [selectedScene, setSelectedScene] = useState<string>('all')

  const { data: kpiData, isLoading: kpiLoading } = useOperationsKpi(selectedDate, selectedDate)
  const { data: trendData, isLoading: trendLoading } = useTrendData()

  const sceneOptions = useMemo(() => {
    if (!trendData) return []
    const labels = [...new Set(trendData.map((d) => d.scene_label))]
    return [{ value: 'all', label: '全部场景' }, ...labels.map((s) => ({ value: s, label: s }))]
  }, [trendData])

  const trendChart = useMemo(() => {
    if (!trendData) return { categories: [], series: [] }

    const filteredTrendData = selectedScene === 'all'
      ? trendData
      : trendData.filter((d) => d.scene_label === selectedScene)

    const timeLabels = [...new Set(filteredTrendData.map((d) => `${d.schedule_date.slice(5)} ${d.day_time_period}`))]

    const sceneLabels = [...new Set(filteredTrendData.map((d) => d.scene_label))]

    const series = sceneLabels.map((scene) => ({
      name: scene,
      data: timeLabels.map((t) => {
        const [date, period] = t.split(' ')
        return filteredTrendData.find((d) => d.schedule_date.slice(5) === date && d.day_time_period === period && d.scene_label === scene)?.people_count || 0
      }),
    }))
    return { categories: timeLabels, series }
  }, [trendData, selectedScene])

  const handleDateChange = (date: Dayjs | null) => {
    setSelectedDate(date ? date.format('YYYY-MM-DD') : dayjs().format('YYYY-MM-DD'))
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <SectionTitle title="会议运营数据" subtitle="实时运营概况与时间维度趋势分析" accentColor={theme.colors.accentGreen} />
        <DatePicker
          defaultValue={dayjs()}
          onChange={handleDateChange}
          allowClear={false}
          size="small"
          suffixIcon={
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={theme.colors.accentGreen} strokeWidth="2">
              <rect x="3" y="4" width="18" height="18" rx="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
          }
          style={{
            flexShrink: 0,
            borderRadius: 6,
          }}
        />
      </div>
      {kpiLoading ? <LoadingSkeleton /> : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
          <KpiCard label="签到人数" value={kpiData?.checkin_count ?? 0} unit="人" color={theme.colors.accentCyan} />
          <KpiCard label="接机人数" value={kpiData?.pickup_count ?? 0} unit="人" color={theme.colors.accentGreen} />
          <KpiCard label="离开人数" value={kpiData?.leave_count ?? 0} unit="人" color={theme.colors.accentRed} />
          <KpiCard label="到院人数" value={kpiData?.hospital_count ?? 0} unit="人" color={theme.colors.accentPurple} />
        </div>
      )}
      <DashboardCard glowColor={theme.colors.accentGreen} title="时间维度数据分析" subtitle="人流热力图 · 会期时间段（上午/下午/晚上）× 关键场景"
        extra={
          <Select
            value={selectedScene}
            onChange={setSelectedScene}
            options={sceneOptions}
            size="small"
            style={{ width: 130, flexShrink: 0 }}
          />
        }
      >
        {trendLoading ? <LoadingSkeleton /> : <MultiLineChart categories={trendChart.categories} series={trendChart.series} height={380} />}
      </DashboardCard>
    </div>
  )
}

export default OperationsSection
