import React from 'react'
import { theme } from '../../styles/theme'
import AnimatedNumber from './AnimatedNumber'

interface KpiCardProps {
  label: string
  value: number
  prefix?: string
  unit?: string
  color?: string
  icon?: React.ReactNode
}

const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  prefix = '',
  unit = '',
  color = theme.colors.accentCyan,
}) => {
  const resolvedColor: string = color
  const colorAttr = resolvedColor === theme.colors.accentRed ? 'red'
    : resolvedColor === theme.colors.accentAmber ? 'amber'
    : resolvedColor === theme.colors.accentGreen ? 'green'
    : resolvedColor === theme.colors.accentPurple ? 'purple'
    : undefined

  return (
    <div
      className="dashboard-card"
      style={{
        background: theme.colors.bgCard,
        borderRadius: theme.cardRadius,
        border: `1px solid ${resolvedColor}20`,
        padding: '22px 20px 20px',
        flex: 1,
        minWidth: 0,
        position: 'relative',
        overflow: 'hidden',
        boxShadow: theme.shadows.card,
      }}
    >
      {/* HUD角标 */}
      <div className="hud-corner hud-corner--tl" data-color={colorAttr} />
      <div className="hud-corner hud-corner--tr" data-color={colorAttr} />
      <div className="hud-corner hud-corner--bl" data-color={colorAttr} />
      <div className="hud-corner hud-corner--br" data-color={colorAttr} />
      {/* 顶部色条 - 更柔和 */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: 2,
        background: `linear-gradient(90deg, ${resolvedColor}cc, ${resolvedColor}40, transparent)`,
        boxShadow: `0 0 8px ${resolvedColor}25`,
      }} />
      {/* 背景装饰数字 */}
      <div style={{
        position: 'absolute',
        bottom: -16,
        right: -6,
        fontSize: 68,
        fontWeight: 900,
        fontFamily: theme.fontDisplay,
        color: `${resolvedColor}05`,
        lineHeight: 1,
        userSelect: 'none',
        pointerEvents: 'none',
      }}>
        {Math.round(value)}
      </div>
      {/* 标签 */}
      <div style={{
        fontSize: 12,
        color: theme.colors.textSecondary,
        marginBottom: 14,
        fontWeight: 500,
        letterSpacing: 0.3,
        lineHeight: 1,
      }}>
        {label}
      </div>
      {/* 数值 */}
      <AnimatedNumber
        value={value}
        prefix={prefix}
        unit={unit}
        style={{
          fontSize: 34,
          fontWeight: 700,
          fontFamily: theme.fontDisplay,
          background: `linear-gradient(175deg, ${resolvedColor}, ${resolvedColor}80)`,
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          letterSpacing: -0.5,
          filter: `drop-shadow(0 0 10px ${resolvedColor}35)`,
          lineHeight: 1.1,
        }}
        unitStyle={{
          fontSize: 13,
          fontWeight: 600,
          color: resolvedColor,
          opacity: 0.6,
          marginLeft: 4,
          fontFamily: theme.fontFamily,
        }}
      />
    </div>
  )
}

export default KpiCard
