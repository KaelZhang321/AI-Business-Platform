import React from 'react'
import { theme } from '../../styles/theme'

interface SectionTitleProps {
  title: string
  subtitle?: string
  accentColor?: string
}

const SectionTitle: React.FC<SectionTitleProps> = ({
  title,
  subtitle,
  accentColor = theme.colors.accentCyan,
}) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 18, position: 'relative' }}>
    {/* 竖条 + 菱形 */}
    <div style={{ display: 'flex', alignItems: 'center', marginRight: 12 }}>
      <div style={{
        width: 3,
        height: 20,
        background: `linear-gradient(180deg, ${accentColor}, ${accentColor}40)`,
        borderRadius: 2,
        boxShadow: `0 0 8px ${accentColor}50`,
      }} />
      <div style={{
        width: 5,
        height: 5,
        background: accentColor,
        transform: 'rotate(45deg)',
        marginLeft: 6,
        boxShadow: `0 0 6px ${accentColor}60`,
      }} />
    </div>
    <div style={{ flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <span style={{
          fontSize: 16,
          fontWeight: 700,
          color: theme.colors.textPrimary,
          letterSpacing: 0.5,
          lineHeight: 1,
        }}>
          {title}
        </span>
        <div style={{
          flex: 1,
          height: 1,
          background: `linear-gradient(90deg, ${accentColor}20, transparent 80%)`,
        }} />
      </div>
      {subtitle && (
        <div style={{
          fontSize: 11,
          color: theme.colors.textSecondary,
          marginTop: 4,
          letterSpacing: 0.2,
        }}>
          {subtitle}
        </div>
      )}
    </div>
  </div>
)

export default SectionTitle
