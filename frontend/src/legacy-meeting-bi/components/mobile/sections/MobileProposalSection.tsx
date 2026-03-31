import React, { useMemo } from 'react'
import { useProposalOverview } from '../../../hooks/useApi'
import MobileCard from '../MobileCard'
import MobileDataTable from '../MobileDataTable'
import LoadingSkeleton from '../../common/LoadingSkeleton'
import type { ProposalRow } from '../../../api/proposal'

const mono = "'JetBrains Mono', monospace"

const EmptyPlaceholder = () => (
  <div style={{ textAlign: 'center', padding: 32 }}>
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#D1D5DB" strokeWidth="1.5" style={{ marginBottom: 8 }}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
    </svg>
    <div style={{ color: '#9CA3AF', fontSize: 13 }}>方案目标数据待录入</div>
  </div>
)

const MobileProposalSection: React.FC = () => {
  const { data: overviewData, isLoading: overviewLoading } = useProposalOverview()

  const overviewColumns = useMemo(() => [
    { title: '方案', dataIndex: 'proposal_type', key: 'type', width: 70 },
    { title: '目标数量', dataIndex: 'target_count', key: 'target', width: 56 },
    {
      title: '目标金额(万)',
      dataIndex: 'target_amount',
      key: 'target_amount',
      width: 88,
      render: (v: number) => <span style={{ color: '#F59E0B', fontWeight: 600, fontFamily: mono }}>¥{Number(v ?? 0).toLocaleString()}</span>,
    },
    {
      title: '实际数量',
      dataIndex: 'actual_count',
      key: 'actual_count',
      width: 60,
      render: (v: number, record: ProposalRow) => (
        <span style={{ color: v >= record.target_count ? '#10B981' : '#EF4444', fontWeight: 600 }}>
          {v}
        </span>
      ),
    },
    {
      title: '实际金额(万)',
      dataIndex: 'actual_amount',
      key: 'actual_amount',
      width: 88,
      render: (v: number) => <span style={{ color: '#10B981', fontWeight: 600, fontFamily: mono }}>¥{Number(v ?? 0).toLocaleString()}</span>,
    },
  ], [])

  if (overviewLoading) return <LoadingSkeleton />

  return (
    <div>
      <MobileCard glowColor="#F59E0B" title="方案概览表" subtitle="各方案目标配置与实际达成">
        {overviewData && overviewData.length > 0 ? (
          <MobileDataTable<ProposalRow> columns={overviewColumns} dataSource={overviewData} rowKey={(r) => `${r.proposal_type}-${r.sub_proposal_type || 'default'}`} />
        ) : (
          <EmptyPlaceholder />
        )}
      </MobileCard>
    </div>
  )
}

export default MobileProposalSection
