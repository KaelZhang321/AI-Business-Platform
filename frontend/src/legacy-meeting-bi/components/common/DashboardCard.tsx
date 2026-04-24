import React from 'react'
import { theme } from '../../styles/theme'

interface DashboardCardProps {
  children: React.ReactNode
  style?: React.CSSProperties
  glowColor?: string
  noPadding?: boolean
  title?: string
  subtitle?: string
  extra?: React.ReactNode
  fill?: boolean
}

const DashboardCard: React.FC<DashboardCardProps> = ({ children, style, glowColor, noPadding, title, subtitle, extra, fill }) => {
  const color = glowColor || theme.colors.accentCyan
  const colorAttr = color === theme.colors.accentRed ? 'red'
    : color === theme.colors.accentAmber ? 'amber'
      : color === theme.colors.accentGreen ? 'green'
        : color === theme.colors.accentPurple ? 'purple'
          : undefined

  return (
    <div
      className="dashboard-card"
      style={{
        background: theme.colors.bgCard,
        borderRadius: theme.cardRadius,
        border: `1px solid ${color}20`,
        padding: noPadding ? 0 : '22px 24px',
        boxShadow: theme.shadows.card,
        position: 'relative',
        overflow: 'hidden',
        ...(fill ? { display: 'flex', flexDirection: 'column' as const } : {}),
        ...style,
        flex: 1
      }}
    >
      {/* HUD 角标 */}
      <div className="hud-corner hud-corner--tl" data-color={colorAttr} />
      <div className="hud-corner hud-corner--tr" data-color={colorAttr} />
      <div className="hud-corner hud-corner--bl" data-color={colorAttr} />
      <div className="hud-corner hud-corner--br" data-color={colorAttr} />
      {/* 顶部光线 */}
      <div className="dashboard-card-top-glow" style={{
        position: 'absolute',
        top: 0,
        left: 20,
        right: 20,
        height: 1,
        background: `linear-gradient(90deg, transparent, ${color}30, transparent)`,
      }} />
      {/* 标题区域 */}
      {title && (
        <div className="dashboard-card-header" style={{
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div className="dashboard-card-header-main" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div className="dashboard-card-header-accent" style={{
              width: 3,
              height: 16,
              borderRadius: 2,
              background: `linear-gradient(180deg, ${color}, ${color}50)`,
              boxShadow: `0 0 6px ${color}40`,
            }} />
            <div>
              <div className="dashboard-card-title" style={{
                fontSize: 14,
                fontWeight: 600,
                color: theme.colors.textPrimary,
                letterSpacing: 0.2,
              }}>
                {title}
              </div>
              {subtitle && (
                <div className="dashboard-card-subtitle" style={{
                  fontSize: 11,
                  color: theme.colors.textSecondary,
                  marginTop: 3,
                  letterSpacing: 0.1,
                }}>
                  {subtitle}
                </div>
              )}
            </div>
          </div>
          {extra}
        </div>
      )}
      {fill ? <div style={{ flex: 1, minHeight: 0 }}>{children}</div> : children}
    </div>
  )
}

export default DashboardCard
