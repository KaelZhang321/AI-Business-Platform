import React, { useMemo } from 'react'
import { useProgress } from '../../hooks/useApi'
import DashboardCard from '../common/DashboardCard'
import LoadingSkeleton from '../common/LoadingSkeleton'
import HorizontalBarChart from '../charts/HorizontalBarChart'
import { theme } from '../../styles/theme'

interface ProgressSectionProps {
  fill?: boolean
}

const ProgressSection: React.FC<ProgressSectionProps> = ({
  fill = false,
}) => {
  const { data, isLoading } = useProgress()

  const chart = useMemo(() => {
    if (!data) return { categories: [], series: [], completionRates: [] }
    return {
      categories: data.items.map((d) => d.region),
      series: [
        { name: '达成金额', data: data.items.map((d) => d.deal_amount) },
        { name: '成交高限', data: data.items.map((d) => d.high_limit) },
      ],
      completionRates: data.items.map((d) => d.completion_rate),
    }
  }, [data])

  if (isLoading || !data) return <LoadingSkeleton />

  return (
    <div
      style={fill ? { height: '100%', width: '100%', display: 'flex', flexDirection: 'column' } : undefined}
    >
      <DashboardCard
        glowColor={theme.colors.accentAmber}
        title="各区域完成度"
        subtitle={`平均完成率: ${data.avg_completion_rate ?? 0}%`}
        fill={fill}
        style={fill ? { flex: 1, minHeight: 0 } : undefined}
      >
        <HorizontalBarChart
          categories={chart.categories}
          series={chart.series}
          completionRates={chart.completionRates}
          height={fill ? '100%' : Math.max(280, data.items.length * 36)}
        />
      </DashboardCard>
    </div>
  )
}

export default ProgressSection
