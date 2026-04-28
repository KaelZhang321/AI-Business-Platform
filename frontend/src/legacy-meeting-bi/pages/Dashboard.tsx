import React, { useMemo, useState } from 'react'
import { DatePicker, Popover, Select } from 'antd'
import { InfoCircleOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import { AnimatePresence, motion } from 'framer-motion'
import PageAchievement from './PageAchievement'
import DistributionBarChart from '../components/charts/DistributionBarChart'
import GroupedBarChart from '../components/charts/GroupedBarChart'
import HorizontalBarChart from '../components/charts/HorizontalBarChart'
import MultiLineChart from '../components/charts/MultiLineChart'
import PieChart from '../components/charts/PieChart'
import DataTable from '../components/common/DataTable'
import LoadingSkeleton from '../components/common/LoadingSkeleton'
import AiChatPanel from '../components/sections/AiChatPanel'
import type { MatrixRow } from '../api/registration'
import { Home } from 'lucide-react'
import { PAGE_PATHS } from '../../navigation'
import { useNavigate } from 'react-router-dom'

import {
  useCustomerProfile,
  useKpiOverview,
  useOperationsKpi,
  useProgress,
  useRegistrationMatrix,
  useSourceDistribution,
  useTrendData,
} from '../hooks/useApi'
import aiIcon from '../styles/AI.png'
import eventLogo from '../styles/logo.png'

const matrixColumns = [
  { title: '大区', dataIndex: 'region', key: 'region', fixed: 'left' as const, width: 80 },
  { title: '千万(报)', dataIndex: 'qianwan_register', key: 'qianwan_register', width: 82 },
  { title: '千万(到)', dataIndex: 'qianwan_arrive', key: 'qianwan_arrive', width: 82 },
  { title: '百万(报)', dataIndex: 'baiwan_register', key: 'baiwan_register', width: 82 },
  { title: '百万(到)', dataIndex: 'baiwan_arrive', key: 'baiwan_arrive', width: 82 },
  { title: '普通(报)', dataIndex: 'putong_register', key: 'putong_register', width: 82 },
  { title: '普通(到)', dataIndex: 'putong_arrive', key: 'putong_arrive', width: 82 },
  { title: '总报名', dataIndex: 'total_register', key: 'total_register', width: 86 },
  { title: '总抵达', dataIndex: 'total_arrive', key: 'total_arrive', width: 86 },
]

const entryTabs = [
  { id: 'customer', label: '客户总览' },
  { id: 'ops', label: '运营数据' },
  { id: 'goal', label: '目标达成' },
] as const

const customerProfileMetricPopover = (
  <div className="metric-info-popover">
    <div className="metric-info-block">
      <div className="metric-info-title">金额等级分布</div>
      <div className="metric-info-desc">定义：统计不同金额等级的客户数量分布。</div>
      <div className="metric-info-desc">口径：按客户等级维度进行分组统计。</div>
    </div>
    <div className="metric-info-block">
      <div className="metric-info-title">身份类型分布</div>
      <div className="metric-info-desc">定义：统计不同参会身份类型的人数分布。</div>
      <div className="metric-info-desc">口径：按参会身份类型维度进行分组统计。</div>
    </div>
    <div className="metric-info-block">
      <div className="metric-info-title">新老客户对比</div>
      <div className="metric-info-desc">定义：统计新顾客、老顾客、陪同等客户类别分布。</div>
      <div className="metric-info-desc">口径：按客户类别维度进行分组统计。</div>
    </div>
  </div>
)

const rightPanelMetricPopover = (
  <div className="metric-info-popover metric-info-popover--small">
    <div className="metric-info-block">
      <div className="metric-info-title">金额等级分布</div>
      <div className="metric-info-desc">定义：统计不同金额等级客户的数量分布。</div>
      <div className="metric-info-desc">口径：按等级分组后进行人数汇总。</div>
    </div>
    <div className="metric-info-block">
      <div className="metric-info-title">任务进展</div>
      <div className="metric-info-desc">定义：展示各区域达成金额与目标高限的完成情况。</div>
      <div className="metric-info-desc">口径：按区域进行横向对比排序。</div>
    </div>
  </div>
)

const metricPopoverByLabel: Record<string, React.ReactNode> = {
  已成交金额: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">已成交金额</div>
      <div className="metric-info-desc">定义：会议期间已发生的新成交金额汇总。</div>
      <div className="metric-info-desc">口径：按成交明细金额累计。</div>
    </div>
  ),
  新规划消耗: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">新规划消耗</div>
      <div className="metric-info-desc">定义：会议期间规划消耗金额汇总。</div>
      <div className="metric-info-desc">口径：按消耗金额字段累计。</div>
    </div>
  ),
  已收款金额: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">已收款金额</div>
      <div className="metric-info-desc">定义：会议期间已回款金额汇总。</div>
      <div className="metric-info-desc">口径：按收款金额字段累计。</div>
    </div>
  ),
  总投资回报率: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">总投资回报率</div>
      <div className="metric-info-desc">定义：衡量投入产出效率的结果型指标。</div>
      <div className="metric-info-desc">预算常量：600（万）。</div>
      <div className="metric-info-desc">计算公式：ROI = 600 ÷ (已成交金额 × 0.4)。</div>
      <div className="metric-info-desc">展示口径：计算结果 × 100 后按百分比展示。</div>
    </div>
  ),
  报名客户: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">报名客户</div>
      <div className="metric-info-desc">定义：已报名客户去重人数。</div>
      <div className="metric-info-desc">口径：按客户唯一标识去重统计。</div>
    </div>
  ),
  已抵达客户: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">已抵达客户</div>
      <div className="metric-info-desc">定义：签到状态为已签到的去重客户人数。</div>
      <div className="metric-info-desc">口径：在报名客户中按签到状态筛选。</div>
    </div>
  ),
  报名抵达率: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">报名抵达率</div>
      <div className="metric-info-desc">定义：报名客户中实际抵达客户的占比。</div>
      <div className="metric-info-desc">口径：已抵达客户 ÷ 报名客户。</div>
    </div>
  ),
  金额等级分布: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">金额等级分布</div>
      <div className="metric-info-desc">定义：统计不同金额等级客户的数量分布。</div>
      <div className="metric-info-desc">口径：按等级维度分组统计。</div>
    </div>
  ),
  身份类型分布: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">身份类型分布</div>
      <div className="metric-info-desc">定义：统计不同参会身份类型的人数分布。</div>
      <div className="metric-info-desc">口径：按身份类型维度分组统计。</div>
    </div>
  ),
  新老客户对比: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">新老客户对比</div>
      <div className="metric-info-desc">定义：统计新顾客、老顾客、陪同等类别分布。</div>
      <div className="metric-info-desc">口径：按客户类别维度分组统计。</div>
    </div>
  ),
  客户来源分布: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">客户来源分布</div>
      <div className="metric-info-desc">定义：统计不同来源渠道的客户数量分布。</div>
      <div className="metric-info-desc">口径：按区域与来源类型分组统计。</div>
    </div>
  ),
  任务进展: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">任务进展</div>
      <div className="metric-info-desc">定义：展示各区域达成金额与目标高限的完成情况。</div>
      <div className="metric-info-desc">口径：按区域进行横向对比。</div>
    </div>
  ),
  金额等级矩阵: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">金额等级矩阵</div>
      <div className="metric-info-desc">定义：展示各区域在不同金额等级下的报名与抵达明细。</div>
      <div className="metric-info-desc">口径：按区域聚合并分等级统计报名/抵达人数。</div>
    </div>
  ),
  签到人数: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">签到人数</div>
      <div className="metric-info-desc">定义：筛选日期内完成签到的去重客户人数。</div>
    </div>
  ),
  接机人数: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">接机人数</div>
      <div className="metric-info-desc">定义：筛选日期内具备接机信息并签到的去重客户人数。</div>
    </div>
  ),
  离开人数: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">离开人数</div>
      <div className="metric-info-desc">定义：筛选日期内离开场景统计人数。</div>
    </div>
  ),
  到院人数: (
    <div className="metric-info-popover metric-info-popover--small">
      <div className="metric-info-title">到院人数</div>
      <div className="metric-info-desc">定义：筛选日期内到院相关场景统计人数。</div>
    </div>
  ),
}

type EntryTab = (typeof entryTabs)[number]['id']

function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return '--'
  if (Math.abs(value) >= 10000) return value.toLocaleString('zh-CN')
  if (Number.isInteger(value)) return value.toLocaleString('zh-CN')
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const renderLabelWithInfo = (label: string, iconAria?: string) => {
  const content = metricPopoverByLabel[label]
  if (!content) return <span>{label}</span>
  return (
    <span className="metric-label-with-info">
      <span>{label}</span>
      <Popover
        content={content}
        trigger="click"
        placement="bottomLeft"
        overlayClassName="metric-info-overlay"
      >
        <button className="metric-inline-info-btn" type="button" aria-label={iconAria || `查看${label}定义`}>
          <InfoCircleOutlined />
        </button>
      </Popover>
    </span>
  )
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [aiOpen, setAiOpen] = useState(false)
  const [entryTab, setEntryTab] = useState<EntryTab>('customer')
  const [selectedScene, setSelectedScene] = useState<string>('all')
  const [selectedDate, setSelectedDate] = useState<string>(dayjs().format('YYYY-MM-DD'))

  const updateTime = dayjs().format('YYYY/MM/DD HH:mm:ss')

  const { data: kpiData, isLoading: kpiLoading } = useKpiOverview()
  const { data: operationsData, isLoading: operationsLoading } = useOperationsKpi(selectedDate, selectedDate)
  const { data: registrationData, isLoading: registrationLoading } = useRegistrationMatrix()
  const { data: trendData, isLoading: trendLoading } = useTrendData()
  const { data: customerProfile, isLoading: profileLoading } = useCustomerProfile()
  const { data: sourceData, isLoading: sourceLoading } = useSourceDistribution()
  const { data: progressData, isLoading: progressLoading } = useProgress()

  const dealAmountItem = kpiData?.deal_amount
  const dealAmountLabel = dealAmountItem?.label || '已成交金额'

  const centerAmount = useMemo(() => {
    if (!dealAmountItem) return '--'
    return `${dealAmountItem.prefix || ''}${formatNumber(dealAmountItem.value)}`
  }, [dealAmountItem])

  const centerUnit = useMemo(() => (dealAmountItem?.unit ? `${dealAmountItem.unit}` : ''), [dealAmountItem])

  const sceneCards = useMemo(() => {
    const fallback = [
      { label: '新规划消耗', value: '--' },
      { label: '已收款金额', value: '--' },
      { label: '总投资回报率', value: '--' },
    ]

    if (!kpiData) return fallback

    const picked = [kpiData.consumed_budget, kpiData.received_amount, kpiData.roi]
    return picked.map((item, idx) => {
      if (!item) return fallback[idx]
      const suffix = item.unit || ''
      const formatted = suffix === '%'
        ? `${formatNumber(item.value)}${suffix}`
        : `${item.prefix || ''}${formatNumber(item.value)}${suffix}`
      return {
        label: item.label || fallback[idx].label,
        value: formatted,
      }
    })
  }, [kpiData])

  const customerStats = useMemo(() => {
    const registeredCustomers = kpiData?.registered_customers.value ?? 0
    const arrivedCustomers = kpiData?.arrived_customers.value ?? 0
    const arrivalRate = registeredCustomers > 0 ? (arrivedCustomers / registeredCustomers) * 100 : 0

    return [
      { label: '报名客户', value: formatNumber(registeredCustomers) },
      { label: '已抵达客户', value: formatNumber(arrivedCustomers) },
      { label: '报名抵达率', value: `${arrivalRate.toFixed(2)}%` },
    ]
  }, [kpiData?.arrived_customers.value, kpiData?.registered_customers.value])

  const operationStats = useMemo(() => {
    const checkin = operationsData?.checkin_count ?? 0
    const pickup = operationsData?.pickup_count ?? 0
    const leave = operationsData?.leave_count ?? 0
    const hospital = operationsData?.hospital_count ?? 0

    return [
      { label: '签到人数', value: `${formatNumber(checkin)} 人` },
      { label: '接机人数', value: `${formatNumber(pickup)} 人` },
      { label: '离开人数', value: `${formatNumber(leave)} 人` },
      { label: '到院人数', value: `${formatNumber(hospital)} 人` },
    ]
  }, [operationsData?.checkin_count, operationsData?.hospital_count, operationsData?.leave_count, operationsData?.pickup_count])

  const handleDateChange = (date: Dayjs | null) => {
    setSelectedDate(date ? date.format('YYYY-MM-DD') : dayjs().format('YYYY-MM-DD'))
  }

  const registrationChart = useMemo(() => {
    if (!registrationData || registrationData.length === 0) {
      return { categories: [] as string[], series: [] as { name: string; data: number[] }[] }
    }
    return {
      categories: registrationData.map((item) => item.region),
      series: [
        { name: '报名人数', data: registrationData.map((item) => item.total_register) },
        { name: '抵达人数', data: registrationData.map((item) => item.total_arrive) },
      ],
    }
  }, [registrationData])

  const sourceDistribution = useMemo(() => {
    if (!sourceData || sourceData.length === 0) return []
    const total = sourceData.reduce((sum, item) => sum + item.customer_count, 0) || 1
    return sourceData
      .map((item) => ({
        name: `${item.region} · ${item.source_type}`,
        value: item.customer_count,
        percentage: (item.customer_count / total) * 100,
      }))
      .sort((a, b) => b.value - a.value)
  }, [sourceData])

  const sceneOptions = useMemo(() => {
    if (!trendData || trendData.length === 0) return [{ value: 'all', label: '全部场景' }]
    const labels = [...new Set(trendData.map((item) => item.scene_label))]
    return [{ value: 'all', label: '全部场景' }, ...labels.map((label) => ({ value: label, label }))]
  }, [trendData])

  const trendChart = useMemo(() => {
    if (!trendData || trendData.length === 0) {
      return { categories: [] as string[], series: [{ name: '客流趋势', data: [] as number[] }] }
    }

    const periodOrder: Record<string, number> = { 上午: 1, 下午: 2, 晚上: 3 }
    const filteredTrendData = selectedScene === 'all'
      ? trendData
      : trendData.filter((item) => item.scene_label === selectedScene)

    const timeLabels = [...new Set(filteredTrendData.map((item) => `${item.schedule_date.slice(5)} ${item.day_time_period}`))]
      .sort((a, b) => {
        const [aDate, aPeriod] = a.split(' ')
        const [bDate, bPeriod] = b.split(' ')
        if (aDate !== bDate) return aDate.localeCompare(bDate)
        return (periodOrder[aPeriod] ?? 99) - (periodOrder[bPeriod] ?? 99)
      })
      .slice(-16)

    const sceneLabels = selectedScene === 'all'
      ? [...new Set(filteredTrendData.map((item) => item.scene_label))]
      : [selectedScene]

    return {
      categories: timeLabels,
      series: sceneLabels.map((scene) => ({
        name: scene,
        data: timeLabels.map((label) => {
          const [date, period] = label.split(' ')
          return filteredTrendData.find((item) =>
            item.schedule_date.slice(5) === date &&
            item.day_time_period === period &&
            item.scene_label === scene
          )?.people_count || 0
        }),
      })),
    }
  }, [selectedScene, trendData])

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

  const isGoalView = entryTab === 'goal'

  return (
    <div className="bigscreen-root">
      <div className="bigscreen-header">
        <div className="bigscreen-brand">
          <div className="bigscreen-brand-dot" />
          <div>
            <div className="bigscreen-brand-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>会议数据分析驾驶舱
              <DynamicHomeButton onClick={() => navigate(PAGE_PATHS['function-square'])} />
            </div>
            <div className="bigscreen-brand-sub">数据更新时间 {updateTime}</div>
          </div>
        </div>
        <div className="bigscreen-center-pill">
          <div className="bigscreen-center-content">
            <img className="bigscreen-center-logo" src={eventLogo} alt="318梅赛尔国际健康节 Logo" />
            <span className="bigscreen-center-text">318梅赛尔国际健康节</span>
          </div>
        </div>
        <div className="entry-switch">
          {entryTabs.map((tab) => (
            <button
              key={tab.id}
              className={`panel-tab-btn ${entryTab === tab.id ? 'active' : ''}`}
              onClick={() => setEntryTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {isGoalView ? (
        <div className="goal-view-shell">
          <motion.div
            className="goal-view-main"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <PageAchievement />
          </motion.div>
        </div>
      ) : (
        <div className="bigscreen-grid">
          <motion.aside
            className="panel-shell"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="panel-header">
              <div className="panel-title-row">
                <div className="panel-title">客户画像分析</div>
                <Popover
                  content={customerProfileMetricPopover}
                  trigger="click"
                  placement="bottomLeft"
                  overlayClassName="metric-info-overlay"
                >
                  <button className="panel-info-btn" type="button" aria-label="查看指标定义">
                    <InfoCircleOutlined />
                  </button>
                </Popover>
              </div>
              <div className="panel-subtitle">客户来源 / 身份类型 / 新老客户</div>
            </div>

            <div className="side-panel-body">
              {profileLoading || !customerProfile ? (
                <LoadingSkeleton />
              ) : (
                <div className="chart-stack chart-stack--left">
                  <div className="mini-chart-card">
                    <div className="mini-chart-title">{renderLabelWithInfo('身份类型分布')}</div>
                    <div className="mini-chart-content">
                      <PieChart data={customerProfile.role_distribution} height="100%" legendAlign="center" labelMode="value" />
                    </div>
                  </div>
                  <div className="mini-chart-card">
                    <div className="mini-chart-title">{renderLabelWithInfo('新老客户对比')}</div>
                    <div className="mini-chart-content">
                      <PieChart data={customerProfile.new_old_distribution} height="100%" legendAlign="center" labelMode="value" />
                    </div>
                  </div>
                  <div className="mini-chart-card">
                    <div className="mini-chart-title">{renderLabelWithInfo('客户来源分布')}</div>
                    {sourceLoading ? (
                      <LoadingSkeleton />
                    ) : (
                      <div className="mini-chart-content">
                        <DistributionBarChart data={sourceDistribution} height="100%" seriesName="客户数" />
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </motion.aside>

          <main className="stage-main">
            <motion.section
              className="hero-card"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="hero-headline">
                <div className="hero-caption">{renderLabelWithInfo(dealAmountLabel)}</div>
                <div className="hero-amount">
                  {kpiLoading ? '--' : centerAmount}
                  <span className="hero-unit">{centerUnit}</span>
                </div>
              </div>
              <div className="hero-divider" />
              <div className="hero-channels">
                {sceneCards.map((item) => (
                  <div className="hero-channel" key={item.label}>
                    <div className="hero-channel-label">{renderLabelWithInfo(item.label)}</div>
                    <div className="hero-channel-value">{item.value}</div>
                  </div>
                ))}
              </div>
            </motion.section>

            {entryTab === 'ops' && (
              <div className="stat-toolbar">
                <div className="trend-subtitle">按日期查询运营指标</div>
                <DatePicker
                  value={dayjs(selectedDate)}
                  onChange={handleDateChange}
                  allowClear={false}
                  size="small"
                  style={{ width: 146 }}
                />
              </div>
            )}
            {(entryTab === 'ops' ? operationsLoading : kpiLoading) ? (
              <LoadingSkeleton />
            ) : (
              <section className={`stat-row ${entryTab === 'ops' ? 'stat-row--four' : 'stat-row--three'}`}>
                {(entryTab === 'ops' ? operationStats : customerStats).map((stat) => (
                  <article className="stat-card" key={stat.label}>
                    <div className="stat-label">{renderLabelWithInfo(stat.label)}</div>
                    <div className="stat-value">{stat.value}</div>
                  </article>
                ))}
              </section>
            )}

            <section className="trend-card">
              {entryTab === 'customer' && (
                <>
                  <div className="trend-title">报名/抵达统计</div>
                  <div className="trend-subtitle">按区域查看报名与抵达人数对比</div>
                  {registrationLoading ? (
                    <LoadingSkeleton />
                  ) : (
                    <>
                      <GroupedBarChart categories={registrationChart.categories} series={registrationChart.series} height={330} />
                      <div style={{ marginTop: 20 }}>
                        <div className="trend-subtitle" style={{ marginBottom: 8 }}>{renderLabelWithInfo('金额等级矩阵')}</div>
                        <DataTable<MatrixRow>
                          columns={matrixColumns}
                          dataSource={registrationData || []}
                          rowKey="region"
                          pagination={{ pageSize: 8, showSizeChanger: false }}
                        />
                      </div>
                    </>
                  )}
                </>
              )}
              {entryTab === 'ops' && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
                    <div>
                      <div className="trend-title">时间维度数据分析</div>
                      <div className="trend-subtitle">人流热力图 · 会期时间段（上午/下午/晚上）× 关键场景</div>
                    </div>
                    <Select
                      value={selectedScene}
                      onChange={setSelectedScene}
                      options={sceneOptions}
                      size="small"
                      style={{ width: 138, flexShrink: 0 }}
                    />
                  </div>
                  {trendLoading ? (
                    <LoadingSkeleton />
                  ) : (
                    <MultiLineChart categories={trendChart.categories} series={trendChart.series} height={420} />
                  )}
                </>
              )}
            </section>
          </main>

          <motion.aside
            className="panel-shell"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="panel-header">
              <div className="panel-title-row">
                <div className="panel-title">金额等级 + 任务进展</div>
                <Popover
                  content={rightPanelMetricPopover}
                  trigger="click"
                  placement="bottomLeft"
                  overlayClassName="metric-info-overlay"
                >
                  <button className="panel-info-btn" type="button" aria-label="查看金额等级与任务进展指标定义">
                    <InfoCircleOutlined />
                  </button>
                </Popover>
              </div>
              <div className="panel-subtitle">金额等级结构与区域完成度</div>
            </div>

            <div className="side-panel-body">
              <div className="chart-stack chart-stack--right">
                <div className="mini-chart-card">
                  <div className="mini-chart-title">{renderLabelWithInfo('金额等级分布')}</div>
                  {profileLoading || !customerProfile ? (
                    <LoadingSkeleton />
                  ) : (
                    <div className="mini-chart-content">
                      <DistributionBarChart data={customerProfile.level_distribution} height="100%" />
                    </div>
                  )}
                </div>
                <div className="mini-chart-card">
                  <div className="mini-chart-title">
                    {renderLabelWithInfo('任务进展')}
                    {progressData?.avg_completion_rate != null ? ` · 平均完成率 ${progressData.avg_completion_rate.toFixed(2)}%` : ''}
                  </div>
                  {progressLoading ? (
                    <LoadingSkeleton />
                  ) : (
                    <div className="mini-chart-content">
                      <HorizontalBarChart
                        categories={progressChart.categories}
                        series={progressChart.series}
                        completionRates={progressChart.completionRates}
                        height="100%"
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          </motion.aside>
        </div>
      )}

      <motion.button
        className="ai-float-btn"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setAiOpen(true)}
      >
        <img src={aiIcon} alt="AI" style={{ width: 64, height: 64, borderRadius: '50%' }} />
      </motion.button>

      <AnimatePresence>
        <AiChatPanel open={aiOpen} onClose={() => setAiOpen(false)} />
      </AnimatePresence>
    </div>
  )
}

function DynamicHomeButton({ onClick }: { onClick: () => void }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <motion.button
      layout
      onClick={onClick}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      onFocus={() => setIsHovered(true)}
      onBlur={() => setIsHovered(false)}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      style={{
        height: 36,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: '9999px',
        background: 'linear-gradient(to right, #4B78EB, #2644A6)',
        color: 'white',
        boxShadow: '0 10px 15px -3px rgba(59, 130, 246, 0.25)',
        overflow: 'hidden',
        border: 'none',
        outline: 'none',
        cursor: 'pointer',
      }}
      initial="idle"
      animate={isHovered ? 'hover' : 'idle'}
      variants={{
        idle: { width: 36, padding: '0 8px' },
        hover: { width: 116, padding: '0 16px', borderRadius: '4px' }
      }}
    >
      {/* Background Shine Effect on Hover */}
      <motion.div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(255, 255, 255, 0.2)',
          pointerEvents: 'none',
        }}
        variants={{
          idle: { opacity: 0 },
          hover: { opacity: 1 },
        }}
      />

      <motion.div layout style={{ display: 'flex', alignItems: 'center', gap: '8px', zIndex: 10, padding: '0 4px' }}>
        <motion.div
          variants={{
            idle: { rotate: 0 },
            hover: { rotate: [0, -15, 15, -10, 10, 0] },
          }}
          transition={{ duration: 0.4 }}
        >
          <Home size={20} style={{ minWidth: 20 }} />
        </motion.div>

        <AnimatePresence>
          {isHovered && (
            <motion.div
              initial={{ opacity: 0, width: 0, filter: 'blur(4px)' }}
              animate={{ opacity: 1, width: 'auto', filter: 'blur(0px)' }}
              exit={{ opacity: 0, width: 0, filter: 'blur(4px)' }}
              transition={{ ease: "easeOut", duration: 0.25 }}
              style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}
            >
              <span style={{ fontWeight: 600, letterSpacing: '0.025em', paddingRight: '4px', fontSize: '14px', lineHeight: 1 }}>
                返回首页
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.button>
  );
}

export default Dashboard
