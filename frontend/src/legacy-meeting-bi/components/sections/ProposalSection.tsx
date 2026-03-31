import React, { useMemo } from 'react'
import { useProposalOverview, useProposalCrossTable } from '../../hooks/useApi'
import DashboardCard from '../common/DashboardCard'
import SectionTitle from '../common/SectionTitle'
import LoadingSkeleton from '../common/LoadingSkeleton'
import DataTable from '../common/DataTable'
import { theme } from '../../styles/theme'
import type { ProposalRow, ProposalCrossRow } from '../../api/proposal'

interface ProposalSectionProps {
  showSectionTitle?: boolean
  showOverview?: boolean
  showCross?: boolean
  reserveSectionTitleSpace?: boolean
}

const overviewColumns = [
  { title: '方案名称', dataIndex: 'proposal_type', key: 'type', width: 180 },
  { title: '目标数量', dataIndex: 'target_count', key: 'target_count', width: 100 },
  {
    title: '目标金额(万)',
    dataIndex: 'target_amount',
    key: 'target_amount',
    width: 120,
    render: (v: number) => <span style={{ color: theme.colors.accentAmber, fontWeight: 600 }}>¥{Number(v ?? 0).toLocaleString()}</span>,
  },
  { title: '实际数量', dataIndex: 'actual_count', key: 'actual_count', width: 100 },
  {
    title: '实际金额(万)',
    dataIndex: 'actual_amount',
    key: 'actual_amount',
    width: 120,
    render: (v: number) => <span style={{ color: theme.colors.accentGreen, fontWeight: 600 }}>¥{Number(v ?? 0).toLocaleString()}</span>,
  },
]

const EmptyPlaceholder = () => (
  <div style={{ textAlign: 'center', padding: 48 }}>
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={theme.colors.textSecondary} strokeWidth="1.5" style={{ opacity: 0.3, marginBottom: 12 }}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
    <div style={{ color: theme.colors.textSecondary, fontSize: 12 }}>方案目标数据待录入</div>
  </div>
)

const ProposalSection: React.FC<ProposalSectionProps> = ({
  showSectionTitle = true,
  showOverview = true,
  showCross = true,
  reserveSectionTitleSpace = false,
}) => {
  const { data: overviewData, isLoading: overviewLoading } = useProposalOverview()
  const { data: crossData, isLoading: crossLoading } = useProposalCrossTable()
  const singleCardMode = [showOverview, showCross].filter(Boolean).length === 1

  // 动态生成交叉表列定义
  const crossColumns = useMemo(() => {
    if (!crossData || crossData.length === 0) return []
    const proposalTypes = [...new Set(crossData.flatMap((r) => Object.keys(r.proposals)))]
    return [
      { title: '大区', dataIndex: 'region', key: 'region' },
      ...proposalTypes.map((pt) => ({
        title: pt,
        key: pt,
        dataIndex: ['proposals', pt] as [string, string],
        render: (v: number) => <span style={{ color: v > 0 ? theme.colors.accentCyan : theme.colors.textSecondary, fontWeight: v > 0 ? 600 : 400 }}>{v ?? 0}</span>,
      })),
    ]
  }, [crossData])

  if (overviewLoading && crossLoading) return <LoadingSkeleton />

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {showSectionTitle && (
        <SectionTitle title="方案目标 VS 达成" subtitle="各成交方案目标与达成" accentColor={theme.colors.accentAmber} />
      )}
      {!showSectionTitle && reserveSectionTitleSpace && (
        <div style={{ visibility: 'hidden' }}>
          <SectionTitle title="方案目标 VS 达成" subtitle="各成交方案目标与达成" accentColor={theme.colors.accentAmber} />
        </div>
      )}
      {showOverview && (
        <DashboardCard
          glowColor={theme.colors.accentAmber}
          title="方案概览表"
          subtitle="各方案目标配置与实际达成"
          fill={singleCardMode}
          style={singleCardMode ? { flex: 1, minHeight: 0 } : undefined}
        >
          {overviewLoading ? <LoadingSkeleton /> : (
            <DataTable<ProposalRow>
              columns={overviewColumns}
              dataSource={overviewData || []}
              rowKey={(r) => `${r.proposal_type}-${r.sub_proposal_type || 'default'}`}
              locale={{ emptyText: '暂无方案目标数据' }}
            />
          )}
        </DashboardCard>
      )}
      {showCross && (
        <DashboardCard
          glowColor={theme.colors.accentAmber}
          title="多维交叉明细表"
          subtitle="各方案在各区域的达成矩阵"
          fill={singleCardMode}
          style={{
            marginTop: showOverview ? 16 : 0,
            ...(singleCardMode ? { flex: 1, minHeight: 0 } : {}),
          }}
        >
          {crossLoading ? <LoadingSkeleton /> : crossData && crossData.length > 0 ? (
            <DataTable<ProposalCrossRow> columns={crossColumns} dataSource={crossData} rowKey="region" />
          ) : (
            <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <EmptyPlaceholder />
            </div>
          )}
        </DashboardCard>
      )}
    </div>
  )
}

export default ProposalSection
