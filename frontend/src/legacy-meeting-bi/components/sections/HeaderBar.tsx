import React, { useMemo, useState } from 'react'
import dayjs from 'dayjs'
import { theme } from '../../styles/theme'



interface HeaderBarProps {
  activeTab: number
  onTabChange: (tab: number) => void
}

const tabs = [
  { id: 0, label: '一 · 客户总览' },
  { id: 1, label: '二 · 运营数据' },
  { id: 2, label: '三 · 目标达成' },
]

const HeaderBar: React.FC<HeaderBarProps> = ({ activeTab, onTabChange }) => {
  const todayStr = useMemo(() => dayjs().format('YYYY-MM-DD'), [])
  return (
    <div style={{ position: 'relative', padding: '20px 0 14px', marginBottom: 8 }}>
      {/* 背景光晕 */}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'radial-gradient(ellipse 50% 120% at 50% -10%, rgba(34,100,238,0.06) 0%, transparent 60%)',
        pointerEvents: 'none',
      }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative' }}>
        {/* 左侧: 标题 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* 装饰图标 */}
          <div style={{ position: 'relative', width: 38, height: 38 }}>
            <div style={{
              position: 'absolute',
              inset: 0,
              border: `1.5px solid ${theme.colors.accentCyan}35`,
              borderRadius: 8,
              transform: 'rotate(45deg)',
            }} />
            <div style={{
              position: 'absolute',
              inset: 5,
              border: `1px solid ${theme.colors.accentCyan}50`,
              borderRadius: 5,
              transform: 'rotate(45deg)',
              background: `${theme.colors.accentCyan}06`,
            }} />
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={theme.colors.accentCyan} strokeWidth="2" style={{ position: 'absolute', top: 10, left: 10, opacity: 0.85 }}>
              <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="m2 17 10 5 10-5" /><path d="m2 12 10 5 10-5" />
            </svg>
          </div>
          <div>
            <h1
              className="glow-text"
              style={{
                fontSize: 24,
                fontWeight: 800,
                fontFamily: theme.fontDisplay,
                color: theme.colors.accentCyan,
                margin: 0,
                letterSpacing: 3,
                lineHeight: 1.2,
              }}
            >
              大会数据分析看板
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={theme.colors.textSecondary} strokeWidth="2" style={{ opacity: 0.7 }}>
                <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
              </svg>
              <span style={{
                fontSize: 12,
                color: theme.colors.textSecondary,
                fontFamily: theme.fontMono,
                letterSpacing: 0.5,
              }}>
                {todayStr}
              </span>
              <div style={{ width: 1, height: 12, background: 'rgba(34,211,238,0.12)' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: theme.colors.accentGreen,
                  animation: 'pulse-glow 2s ease-in-out infinite',
                }} />
                <span style={{
                  fontSize: 10,
                  color: theme.colors.accentGreen,
                  fontWeight: 700,
                  fontFamily: theme.fontMono,
                  letterSpacing: 1,
                }}>
                  LIVE
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 右侧: 导航菜单 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {tabs.map((tab) => (
              <button
                key={tab.id}
                className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => onTabChange(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default HeaderBar
