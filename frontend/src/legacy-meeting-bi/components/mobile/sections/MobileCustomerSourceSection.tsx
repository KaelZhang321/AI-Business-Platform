import React, { useMemo } from 'react'
import { useProgress, useSourceDistribution } from '../../../hooks/useApi'
import MobileCard from '../MobileCard'
import LoadingSkeleton from '../../common/LoadingSkeleton'
import StackedBarChart from '../../charts/StackedBarChart'
import HorizontalBarChart from '../../charts/HorizontalBarChart'

const MobileCustomerSourceSection: React.FC = () => {
  const { data: sourceData, isLoading: srcLoading } = useSourceDistribution()
  const { data: progressData, isLoading: progressLoading } = useProgress()

  const sourceChart = useMemo(() => {
    if (!sourceData) return { categories: [], series: [] }
    const regionTotals = sourceData.reduce<Record<string, number>>((acc, item) => {
      acc[item.region] = (acc[item.region] || 0) + item.customer_count
      return acc
    }, {})
    const regions = Object.entries(regionTotals)
      .sort((a, b) => b[1] - a[1])
      .map(([region]) => region)
    const types = [...new Set(sourceData.map((d) => d.source_type))]
    const series = types.map((t) => ({
      name: t,
      data: regions.map((r) => sourceData.find((d) => d.region === r && d.source_type === t)?.customer_count || 0),
    }))
    return { categories: regions, series }
  }, [sourceData])

  const progressChart = useMemo(() => {
    if (!progressData) {
      return { categories: [] as string[], series: [] as { name: string; data: number[] }[], completionRates: [] as Array<number | null | undefined> }
    }
    return {
      categories: progressData.items.map((item) => item.region),
      series: [
        { name: '达成金额', data: progressData.items.map((item) => item.deal_amount) },
        { name: '成交高限', data: progressData.items.map((item) => item.high_limit) },
      ],
      completionRates: progressData.items.map((item) => item.completion_rate),
    }
  }, [progressData])

  if (srcLoading) return <LoadingSkeleton />

  return (
    <div>
      <MobileCard
        glowColor="#10B981"
        title="客户来源分布"
        subtitle="按区域与来源类型对比"
      >
        <StackedBarChart categories={sourceChart.categories} series={sourceChart.series} height={260} />
      </MobileCard>
      <div style={{ height: 12 }} />
      <MobileCard
        glowColor="#10B981"
        title="任务进展"
        subtitle={progressData?.avg_completion_rate != null ? `平均完成率 ${progressData.avg_completion_rate.toFixed(2)}%` : '各区域任务完成度'}
      >
        {progressLoading ? (
          <LoadingSkeleton />
        ) : (
          <HorizontalBarChart
            categories={progressChart.categories}
            series={progressChart.series}
            completionRates={progressChart.completionRates}
            height={260}
          />
        )}
      </MobileCard>
    </div>
  )
}

export default MobileCustomerSourceSection
