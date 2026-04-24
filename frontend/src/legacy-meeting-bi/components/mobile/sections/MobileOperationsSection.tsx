import React, { useMemo, useState } from 'react'
import { DatePicker, Select } from 'antd'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import { useOperationsKpi, useTrendData } from '../../../hooks/useApi'
import MobileCard from '../MobileCard'
import MobileKpiCard from '../MobileKpiCard'
import LoadingSkeleton from '../../common/LoadingSkeleton'
import MultiLineChart from '../../charts/MultiLineChart'

const MobileOperationsSection: React.FC = () => {
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', marginBottom: 14 }}>
        <DatePicker
          defaultValue={dayjs()}
          onChange={handleDateChange}
          allowClear={false}
          size="small"
          style={{ flexShrink: 0, borderRadius: 8 }}
        />
      </div>
      {kpiLoading ? <LoadingSkeleton /> : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <MobileKpiCard label="签到人数" value={kpiData?.checkin_count ?? 0} unit="人" color="#3B82F6" />
          <MobileKpiCard label="接机人数" value={kpiData?.pickup_count ?? 0} unit="人" color="#10B981" />
          <MobileKpiCard label="离开人数" value={kpiData?.leave_count ?? 0} unit="人" color="#EF4444" />
          <MobileKpiCard label="到院人数" value={kpiData?.hospital_count ?? 0} unit="人" color="#8B5CF6" />
        </div>
      )}
      <MobileCard
        glowColor="#10B981"
        title="时间维度数据分析"
        subtitle="人流热力图 · 会期时间段（上午/下午/晚上）× 关键场景"
        extra={
          <Select
            value={selectedScene}
            onChange={setSelectedScene}
            options={sceneOptions}
            size="small"
            style={{ width: 100, flexShrink: 0 }}
          />
        }
      >
        {trendLoading ? <LoadingSkeleton /> : <MultiLineChart categories={trendChart.categories} series={trendChart.series} height={280} />}
      </MobileCard>
    </div>
  )
}

export default MobileOperationsSection
