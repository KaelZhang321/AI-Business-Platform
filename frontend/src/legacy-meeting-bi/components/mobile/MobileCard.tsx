import React from 'react'
import { Popover } from 'antd'
import { InfoCircleOutlined } from '@ant-design/icons'
import { getMetricInfoContent } from './metricInfo'

interface MobileCardProps {
  children: React.ReactNode
  title?: string
  subtitle?: string
  glowColor?: string
  extra?: React.ReactNode
  style?: React.CSSProperties
}

const MobileCard: React.FC<MobileCardProps> = ({ children, title, subtitle, glowColor: _glowColor, extra, style }) => {
  const matrixBaseColor = '#3B82F6'
  const color = matrixBaseColor
  const metricInfo = title ? getMetricInfoContent(title) : undefined
  return (
    <div className="mobile-card" style={{ ...style, ['--mobile-card-accent' as string]: color }}>
      {title && (
        <div className="mobile-card-head">
          <div className="mobile-card-head-main">
            <div className="mobile-card-head-accent" />
            <div style={{ minWidth: 0 }}>
              <div className="mobile-card-title">
                <span>{title}</span>
                {metricInfo && (
                  <Popover content={metricInfo} trigger="click" placement="bottomLeft" overlayClassName="mobile-metric-info-overlay">
                    <button className="mobile-metric-info-btn" type="button" aria-label={`查看${title}说明`}>
                      <InfoCircleOutlined />
                    </button>
                  </Popover>
                )}
              </div>
              {subtitle && (
                <div className="mobile-card-subtitle">
                  {subtitle}
                </div>
              )}
            </div>
          </div>
          {extra}
        </div>
      )}
      {children}
    </div>
  )
}

export default MobileCard
