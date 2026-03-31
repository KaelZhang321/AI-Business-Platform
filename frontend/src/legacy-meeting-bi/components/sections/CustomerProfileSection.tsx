import React from 'react'
import { useCustomerProfile } from '../../hooks/useApi'
import DashboardCard from '../common/DashboardCard'
import SectionTitle from '../common/SectionTitle'
import LoadingSkeleton from '../common/LoadingSkeleton'
import PieChart from '../charts/PieChart'
import DistributionBarChart from '../charts/DistributionBarChart'
import { theme } from '../../styles/theme'

const CustomerProfileSection: React.FC = () => {
  const { data, isLoading } = useCustomerProfile()
  if (isLoading || !data) return <LoadingSkeleton />
  const levelChartHeight = Math.max(320, data.level_distribution.length * 30 + 72)

  return (
    <div>
      <SectionTitle title="客户画像分析" subtitle="客户金额等级、身份类型、新老客户三维画像" accentColor={theme.colors.accentPurple} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 }}>
        <DashboardCard glowColor={theme.colors.accentCyan} title="金额等级分布">
          <DistributionBarChart data={data.level_distribution} height={levelChartHeight} />
        </DashboardCard>
        <DashboardCard glowColor={theme.colors.accentPurple} title="身份类型分布" fill style={{ height: '100%' }}>
          <div style={{ flex: 1, minHeight: 0, width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <PieChart data={data.role_distribution} height={280} legendAlign="center" labelMode="value" />
          </div>
        </DashboardCard>
        <DashboardCard glowColor={theme.colors.accentGreen} title="新老客户对比" fill style={{ height: '100%' }}>
          <div style={{ flex: 1, minHeight: 0, width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <PieChart data={data.new_old_distribution} height={280} legendAlign="center" labelMode="value" />
          </div>
        </DashboardCard>
      </div>
    </div>
  )
}

export default CustomerProfileSection
