import React from 'react'
import { useCustomerProfile } from '../../../hooks/useApi'
import MobileCard from '../MobileCard'
import LoadingSkeleton from '../../common/LoadingSkeleton'
import PieChart from '../../charts/PieChart'
import DistributionBarChart from '../../charts/DistributionBarChart'

const MobileCustomerProfileSection: React.FC = () => {
  const { data, isLoading } = useCustomerProfile()
  if (isLoading || !data) return <LoadingSkeleton />
  const levelChartHeight = Math.max(260, data.level_distribution.length * 26 + 72)

  return (
    <div>
      <MobileCard glowColor="#10B981" title="金额等级分布" subtitle="各等级客户数量占比">
        <DistributionBarChart data={data.level_distribution} height={levelChartHeight} />
      </MobileCard>
      <div style={{ height: 12 }} />
      <MobileCard glowColor="#10B981" title="身份类型分布" subtitle="客户身份结构分布">
        <PieChart data={data.role_distribution} height={220} legendAlign="center" labelMode="value" />
      </MobileCard>
      <div style={{ height: 12 }} />
      <MobileCard glowColor="#10B981" title="新老客户对比" subtitle="新客与老客占比对比">
        <PieChart data={data.new_old_distribution} height={220} legendAlign="center" labelMode="value" />
      </MobileCard>
    </div>
  )
}

export default MobileCustomerProfileSection
