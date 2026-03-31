import React from 'react'
import { theme } from '../../styles/theme'

export interface RankingItem {
  name: string
  value: number
  extra?: string
}

interface RankingPanelProps {
  title: string
  subtitle?: string
  items: RankingItem[]
  valueLabel?: string
  color?: string
  maxValue?: number
  formatValue?: (v: number) => string
  onItemClick?: (item: RankingItem, index: number) => void
}

const medalColors = ['#FFD700', '#C0C0C0', '#CD7F32']

const RankingPanel: React.FC<RankingPanelProps> = ({
  title,
  subtitle,
  items,
  valueLabel = '数值',
  color = theme.colors.accentCyan,
  maxValue,
  formatValue,
  onItemClick,
}) => {
  const max = maxValue || Math.max(...items.map((i) => i.value), 1)
  const fmt = formatValue || ((v: number) => v.toLocaleString())
  const isInteractive = Boolean(onItemClick)

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(8, 25, 60, 0.8) 0%, rgba(10, 29, 69, 0.65) 100%)',
      borderRadius: theme.cardRadius,
      border: `1px solid ${color}18`,
      padding: '18px 16px',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      boxShadow: theme.shadows.card,
      position: 'relative',
    }}>
      {/* 顶部光线 */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 16,
        right: 16,
        height: 1,
        background: `linear-gradient(90deg, transparent, ${color}30, transparent)`,
      }} />

      {/* 标题 */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 3,
            height: 14,
            borderRadius: 2,
            background: `linear-gradient(180deg, ${color}, ${color}50)`,
            boxShadow: `0 0 6px ${color}40`,
          }} />
          <span style={{
            fontSize: 14,
            fontWeight: 600,
            color: theme.colors.textPrimary,
            letterSpacing: 0.3,
          }}>
            {title}
          </span>
        </div>
        {subtitle && (
          <div style={{
            fontSize: 11,
            color: theme.colors.textSecondary,
            marginTop: 4,
            marginLeft: 11,
          }}>
            {subtitle}
          </div>
        )}
      </div>

      {/* 列头 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        padding: '0 4px 8px',
        borderBottom: `1px solid ${color}10`,
        marginBottom: 4,
      }}>
        <span style={{ width: 28, fontSize: 10, color: theme.colors.textTertiary, fontWeight: 600, textTransform: 'uppercase' as const }}>
          #
        </span>
        <span style={{ flex: 1, fontSize: 10, color: theme.colors.textTertiary, fontWeight: 600, textTransform: 'uppercase' as const }}>
          名称
        </span>
        <span style={{ fontSize: 10, color: theme.colors.textTertiary, fontWeight: 600, textTransform: 'uppercase' as const, textAlign: 'right' as const }}>
          {valueLabel}
        </span>
      </div>

      {/* 列表 */}
      <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        {items.map((item, i) => {
          const isTop3 = i < 3
          const barWidth = max > 0 ? (item.value / max) * 100 : 0

          return (
            <div
              key={item.name}
              onClick={() => onItemClick?.(item, i)}
              onKeyDown={isInteractive ? (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onItemClick?.(item, i)
                }
              } : undefined}
              role={isInteractive ? 'button' : undefined}
              tabIndex={isInteractive ? 0 : undefined}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '8px 4px',
                borderRadius: 4,
                cursor: onItemClick ? 'pointer' : 'default',
                transition: 'background 0.2s',
                position: 'relative',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = `${color}08`
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
            >
              {/* 排名序号 */}
              <div style={{
                width: 28,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                {isTop3 ? (
                  <div style={{
                    width: 20,
                    height: 20,
                    borderRadius: '50%',
                    background: `linear-gradient(135deg, ${medalColors[i]}, ${medalColors[i]}88)`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 11,
                    fontWeight: 700,
                    fontFamily: theme.fontMono,
                    color: '#fff',
                    boxShadow: `0 0 8px ${medalColors[i]}40`,
                  }}>
                    {i + 1}
                  </div>
                ) : (
                  <span style={{
                    fontSize: 12,
                    fontWeight: 500,
                    fontFamily: theme.fontMono,
                    color: theme.colors.textTertiary,
                  }}>
                    {i + 1}
                  </span>
                )}
              </div>

              {/* 名称 + 进度条 */}
              <div style={{ flex: 1, minWidth: 0, marginRight: 8 }}>
                <div style={{
                  fontSize: 13,
                  fontWeight: isTop3 ? 600 : 400,
                  color: isTop3 ? theme.colors.textPrimary : theme.colors.textSecondary,
                  marginBottom: 4,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}>
                  {item.name}
                </div>
                <div style={{
                  height: 3,
                  borderRadius: 2,
                  background: `${color}10`,
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${barWidth}%`,
                    borderRadius: 2,
                    background: isTop3
                      ? `linear-gradient(90deg, ${color}, ${color}cc)`
                      : `linear-gradient(90deg, ${color}60, ${color}30)`,
                    transition: 'width 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
                  }} />
                </div>
              </div>

              {/* 数值 */}
              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <span style={{
                  fontSize: 14,
                  fontWeight: 700,
                  fontFamily: theme.fontMono,
                  color: isTop3 ? color : theme.colors.textPrimary,
                }}>
                  {fmt(item.value)}
                </span>
                {item.extra && (
                  <div style={{
                    fontSize: 10,
                    color: theme.colors.textTertiary,
                    marginTop: 1,
                  }}>
                    {item.extra}
                  </div>
                )}
              </div>
            </div>
          )
        })}
        {items.length === 0 && (
          <div style={{
            textAlign: 'center',
            padding: '32px 0',
            color: theme.colors.textTertiary,
            fontSize: 12,
          }}>
            暂无数据
          </div>
        )}
      </div>
    </div>
  )
}

export default RankingPanel
