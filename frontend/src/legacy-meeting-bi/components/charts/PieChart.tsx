import React, { useEffect, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import { baseOption, chartPalette } from './echarts-config'
import { theme } from '../../styles/theme'

interface PieChartProps {
  data: { name: string; value: number }[]
  title?: string
  height?: number | string
  legendAlign?: 'left' | 'center' | 'right'
  labelMode?: 'percent' | 'value'
}

const PieChart: React.FC<PieChartProps> = ({
  data,
  title,
  height = 260,
  legendAlign = 'right',
  labelMode = 'percent',
}) => {
  const chartRef = useRef<ReactECharts>(null)
  const resolvedHeightProp: number | string = height
  const isFluid = typeof resolvedHeightProp === 'string' && resolvedHeightProp === '100%'
  const numericHeight = typeof resolvedHeightProp === 'number' ? resolvedHeightProp : 260
  const isCompact = numericHeight <= 220
  const legendPosition = legendAlign === 'left'
    ? { left: 0 }
    : legendAlign === 'center'
      ? { left: 'center' as const }
      : { right: 0 }

  useEffect(() => {
    if (!isFluid) return
    const el = chartRef.current?.getEchartsInstance()?.getDom()
    if (!el) return
    const ro = new ResizeObserver(() => {
      chartRef.current?.getEchartsInstance()?.resize()
    })
    ro.observe(el.parentElement || el)
    return () => ro.disconnect()
  }, [isFluid])

  const option = {
    ...baseOption,
    color: chartPalette,
    title: title
      ? { text: title, left: 'center', top: 0, textStyle: { color: theme.colors.textPrimary, fontSize: 13, fontWeight: 600, fontFamily: theme.fontFamily } }
      : undefined,
    tooltip: {
      ...baseOption.tooltip,
      trigger: 'item' as const,
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      ...baseOption.legend,
      orient: 'horizontal' as const,
      ...legendPosition,
      bottom: isCompact ? 0 : 4,
      itemWidth: 8,
      itemHeight: 8,
      itemGap: isCompact ? 12 : 16,
      icon: 'circle',
      textStyle: { color: '#8896B3', fontSize: isCompact ? 10 : 11, fontFamily: theme.fontFamily },
    },
    series: [
      {
        type: 'pie' as const,
        radius: isCompact ? ['40%', '66%'] : ['42%', '68%'],
        center: isCompact ? ['50%', '44%'] : ['50%', '46%'],
        avoidLabelOverlap: true,
        data,
        label: {
          show: true,
          formatter: (params: { value?: number; percent?: number }) => {
            if (labelMode === 'value') return `${(params.value ?? 0).toLocaleString()}`
            return `${(params.percent ?? 0).toFixed(0)}%`
          },
          color: '#8896B3',
          fontSize: 10,
          fontFamily: theme.fontMono,
        },
        labelLine: {
          lineStyle: { color: 'rgba(136,150,179,0.2)' },
          length: 8,
          length2: 12,
        },
        itemStyle: {
          borderColor: 'transparent',
          borderWidth: 0,
          shadowBlur: 8,
          shadowColor: 'rgba(63,101,224,0.16)',
        },
        emphasis: {
          scale: true,
          scaleSize: 4,
          itemStyle: {
            shadowBlur: 20,
            shadowColor: 'rgba(34,211,238,0.3)',
          },
        },
      },
    ],
  }

  return <ReactECharts ref={chartRef} option={option} style={{ width: '100%', height: resolvedHeightProp }} {...(isFluid ? { opts: { height: 'auto' } } : {})} />
}

export default PieChart
