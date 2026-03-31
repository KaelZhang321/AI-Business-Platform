import React, { useRef, useEffect } from 'react'
import ReactECharts from 'echarts-for-react'
import { baseOption, axisStyle, chartPalette } from './echarts-config'

interface GroupedBarChartProps {
  categories: string[]
  series: { name: string; data: number[] }[]
  height?: number | string
  onBarClick?: (params: { name?: string; seriesName?: string }) => void
}

const GroupedBarChart: React.FC<GroupedBarChartProps> = ({ categories, series, height = 320, onBarClick }) => {
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

  const option = {
    ...baseOption,
    color: chartPalette,
    tooltip: { ...baseOption.tooltip, trigger: 'axis' as const },
    legend: { ...baseOption.legend, top: 0, itemGap: 16 },
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
      barWidth: '22%',
      barGap: '30%',
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: chartPalette[i % chartPalette.length] },
            { offset: 1, color: `${chartPalette[i % chartPalette.length]}55` },
          ],
        },
        shadowBlur: 6,
        shadowColor: `${chartPalette[i % chartPalette.length]}18`,
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

export default GroupedBarChart
