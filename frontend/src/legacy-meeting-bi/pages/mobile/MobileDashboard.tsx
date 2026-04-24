import React, { useState } from 'react'
import { ConfigProvider } from 'antd'
import { motion, AnimatePresence, type Variants } from 'framer-motion'
import { useKpiOverview } from '../../hooks/useApi'
import MobileHeader from '../../components/mobile/MobileHeader'
import MobileTabBar from '../../components/mobile/MobileTabBar'
import MobileKpiCard from '../../components/mobile/MobileKpiCard'
import MobilePageCustomer from './MobilePageCustomer'
import MobilePageOperations from './MobilePageOperations'
import MobilePageAchievement from './MobilePageAchievement'
import AiChatPanel from '../../components/sections/AiChatPanel'
import aiIcon from '../../styles/AI.png'
import { legacyEase } from '../../utils/motion'

const mobileKpiColors: Record<string, string> = {
  报名客户: '#3B82F6',
  已抵达客户: '#10B981',
  已成交金额: '#4E6BFF',
  新规划消耗: '#18B7A0',
  已收款金额: '#8B5CF6',
  总投资回报率: '#06B6D4',
}

const pages = [MobilePageCustomer, MobilePageOperations, MobilePageAchievement]

const pageVariants: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: legacyEase } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.15 } },
}

const mobileLightTheme = {
  token: {
    colorPrimary: '#2E64F6',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBgLayout: '#F3F6FC',
    colorText: '#162038',
    colorTextSecondary: '#6C7895',
    colorBorder: '#DFE7F3',
    colorBorderSecondary: '#ECF1F8',
    borderRadius: 12,
    fontFamily: "'Noto Sans SC', 'Saira Semi Condensed', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    fontSize: 13,
  },
  components: {
    Table: {
      headerBg: '#F5F8FE',
      headerColor: '#6C7895',
      rowHoverBg: '#F6F9FF',
      borderColor: '#EAF0F8',
      colorBgContainer: '#FFFFFF',
      cellFontSize: 13,
      headerFontSize: 11,
    },
    Skeleton: {
      color: '#EAF0F8',
      colorGradientEnd: '#DCE7F6',
    },
    Select: {
      optionSelectedBg: '#ECF3FF',
      optionSelectedColor: '#2E64F6',
      optionActiveBg: '#F5F8FE',
      selectorBg: '#F5F8FE',
      colorBorder: '#DFE7F3',
    },
    DatePicker: {
      colorBgContainer: '#F5F8FE',
      colorBorder: '#DFE7F3',
    },
    Drawer: {
      colorBgElevated: '#FFFFFF',
    },
  },
}

const MobileDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0)
  const [aiOpen, setAiOpen] = useState(false)
  const { data: kpiData, isLoading: kpiLoading } = useKpiOverview()
  const ActivePage = pages[activeTab]

  const kpiItems = kpiData
    ? [kpiData.deal_amount, kpiData.consumed_budget, kpiData.arrived_customers, kpiData.registered_customers, kpiData.received_amount, kpiData.roi]
    : []
  const primaryKpis = kpiItems.slice(0, 2)
  const secondaryKpis = kpiItems.slice(2)

  return (
    <ConfigProvider theme={mobileLightTheme}>
      <div className="mobile-container">
        <MobileHeader />
        <div className="mobile-content">
          {/* KPI 网格 */}
          {kpiLoading ? (
            <div style={{ padding: '4px 0 14px' }}>
              <div style={{ background: '#fff', borderRadius: 14, padding: 16, border: '1px solid #DFE7F3' }}>
                <div style={{ height: 60, background: '#EAF0F8', borderRadius: 10, animation: 'skeleton-pulse 1.8s ease-in-out infinite' }} />
              </div>
            </div>
          ) : (
            <>
              <div className="mobile-kpi-grid mobile-kpi-grid--primary">
                {primaryKpis.map((item) => (
                  <MobileKpiCard
                    key={item.label}
                    label={item.label}
                    value={item.value}
                    prefix={item.prefix}
                    unit={item.unit}
                    color={mobileKpiColors[item.label]}
                    featured
                  />
                ))}
              </div>
              <div className="mobile-kpi-secondary-panel">
                <div className="mobile-kpi-grid mobile-kpi-grid--secondary">
                  {secondaryKpis.map((item) => (
                    <MobileKpiCard
                      key={item.label}
                      label={item.label}
                      value={item.value}
                      prefix={item.prefix}
                      unit={item.unit}
                      color={mobileKpiColors[item.label]}
                      compact
                    />
                  ))}
                </div>
              </div>
            </>
          )}

          {/* 页面内容 */}
          <div className="mobile-page-shell">
            <AnimatePresence mode="wait">
              <motion.div key={activeTab} variants={pageVariants} initial="initial" animate="animate" exit="exit">
                <ActivePage />
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
        <MobileTabBar activeTab={activeTab} onTabChange={setActiveTab} />

        {/* AI 浮动按钮 */}
        <button className="mobile-ai-fab" onClick={() => setAiOpen(true)}>
          <img src={aiIcon} alt="AI" style={{ width: 52, height: 52 }} />
        </button>

        {/* AI 聊天面板 */}
        <AiChatPanel open={aiOpen} onClose={() => setAiOpen(false)} light />
      </div>
    </ConfigProvider>
  )
}

export default MobileDashboard
