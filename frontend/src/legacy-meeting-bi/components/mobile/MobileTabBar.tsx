import React from 'react'

interface MobileTabBarProps {
  activeTab: number
  onTabChange: (tab: number) => void
}

const tabs = [
  {
    label: '客户总览',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  {
    label: '运营数据',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
  },
  {
    label: '目标达成',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20V10" />
        <path d="M18 20V4" />
        <path d="M6 20v-4" />
      </svg>
    ),
  },
]

const MobileTabBar: React.FC<MobileTabBarProps> = ({ activeTab, onTabChange }) => (
  <div className="mobile-tabbar">
    {tabs.map((tab, i) => (
      <button
        key={i}
        className={`mobile-tabbar-item ${activeTab === i ? 'mobile-tabbar-item--active' : 'mobile-tabbar-item--inactive'}`}
        onClick={() => onTabChange(i)}
      >
        <span className="mobile-tabbar-item__icon-wrap">
          {tab.icon}
        </span>
        <span>{tab.label}</span>
      </button>
    ))}
  </div>
)

export default MobileTabBar
