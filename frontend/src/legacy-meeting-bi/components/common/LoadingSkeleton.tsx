import React from 'react'
import { Skeleton } from 'antd'
import DashboardCard from './DashboardCard'

const LoadingSkeleton: React.FC = () => (
  <DashboardCard>
    <Skeleton active paragraph={{ rows: 4 }} />
  </DashboardCard>
)

export default LoadingSkeleton
