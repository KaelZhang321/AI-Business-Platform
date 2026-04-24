import React from 'react'
import { useKpiOverview } from '../../hooks/useApi'
import KpiCard from '../common/KpiCard'
import LoadingSkeleton from '../common/LoadingSkeleton'
import { theme } from '../../styles/theme'

const colorMap: Record<string, string> = {
  报名客户: theme.colors.accentCyan,
  已抵达客户: theme.colors.accentGreen,
  已成交金额: theme.colors.accentAmber,
  新规划消耗: theme.colors.accentRed,
  已收款金额: theme.colors.accentPurple,
  总投资回报率: '#38BDF8',
}

const CoreKpiRow: React.FC = () => {
  const { data, isLoading } = useKpiOverview()
  if (isLoading || !data) return <LoadingSkeleton />
  const items = [data.registered_customers, data.arrived_customers, data.deal_amount, data.consumed_budget, data.received_amount, data.roi]
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 16 }}>
        {items.map((item) => (
          <KpiCard key={item.label} label={item.label} value={item.value} prefix={item.prefix} unit={item.unit} color={colorMap[item.label]} />
        ))}
      </div>
    </div>
  )
}

export default CoreKpiRow
