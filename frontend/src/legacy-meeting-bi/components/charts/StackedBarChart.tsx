import React, { useRef, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import { baseOption, axisStyle, chartPalette } from './echarts-config'

interface StackedBarChartProps {
  categories: string[]
  series: { name: string; data: number[]; stack?: string }[]
  height?: number | string
  onBarClick?: (params: { name?: string; seriesName?: string }) => void
}

const StackedBarChart: React.FC<StackedBarChartProps> = ({ categories, series, height = 320, onBarClick }) => {
  const chartRef = useRef<ReactECharts>(null)
  const resolvedHeightProp: number | string = height
  const isFluid = typeof resolvedHeightProp === 'string' && resolvedHeightProp === '100%'

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

  const manyLegends = series.length > 6
  const option = {
    ...baseOption,
    color: chartPalette,
    tooltip: { ...baseOption.tooltip, trigger: 'axis' as const },
    legend: {
      ...baseOption.legend,
      top: 0,
      itemGap: manyLegends ? 10 : 16,
      ...(manyLegends ? { type: 'scroll' as const, pageIconColor: '#8896B3', pageTextStyle: { color: '#8896B3' } } : {}),
    },
    grid: { ...baseOption.grid, top: manyLegends ? 36 : 40 },
    xAxis: {
      type: 'category' as const,
      data: categories,
      ...axisStyle,
      axisLabel: { ...axisStyle.axisLabel, rotate: categories.length > 8 ? 30 : 0, interval: 0 },
    },
    yAxis: { type: 'value' as const, ...axisStyle },
    series: series.map((s, i) => ({
      ...s,
      type: 'bar' as const,
      stack: s.stack || 'total',
      barWidth: '35%',
      itemStyle: {
        borderRadius: i === series.length - 1 ? [4, 4, 0, 0] : 0,
        shadowBlur: 4,
        shadowColor: 'rgba(0,0,0,0.2)',
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 14,
          shadowColor: `${chartPalette[i % chartPalette.length]}35`,
        },
      },
    })),
  }

  const onEvents = onBarClick ? { click: (p: { name?: string; seriesName?: string }) => onBarClick(p) } : undefined
  return <ReactECharts ref={chartRef} option={option} notMerge style={{ height: resolvedHeightProp, cursor: onBarClick ? 'pointer' : undefined }} onEvents={onEvents} {...(isFluid ? { opts: { height: 'auto' } } : {})} />
}

export default StackedBarChart
