import React, { useEffect, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import { baseOption, axisStyle, chartPalette } from './echarts-config'

interface HorizontalBarChartProps {
  categories: string[]
  series: { name: string; data: number[] }[]
  height?: number | string
  completionRates?: Array<number | null | undefined>
}

const HorizontalBarChart: React.FC<HorizontalBarChartProps> = ({ categories, series, height = 350, completionRates }) => {
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
    tooltip: {
      ...baseOption.tooltip,
      trigger: 'axis' as const,
      formatter: (params: Array<{ axisValue: string; seriesName: string; value: number; color: string; dataIndex: number }>) => {
        const region = params[0]?.axisValue ?? ''
        const completionRate = completionRates?.[params[0]?.dataIndex ?? 0]
        const rows = params.map((item) => `
          <div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:4px;">
            <span style="display:flex;align-items:center;gap:6px;">
              <span style="width:8px;height:8px;border-radius:999px;background:${item.color};box-shadow:0 0 8px ${item.color}55;"></span>
              <span>${item.seriesName}</span>
            </span>
            <strong style="color:#E2E8F0;">${item.value.toLocaleString()}</strong>
          </div>
        `).join('')

        return `
          <div style="min-width:180px;">
            <div style="font-weight:700;color:#E2E8F0;margin-bottom:8px;">${region}</div>
            ${rows}
            <div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:8px;padding-top:8px;border-top:1px solid rgba(34,211,238,0.08);">
              <span style="color:#94A3B8;">完成度</span>
              <strong style="color:#FBBF24;">${completionRate == null ? '-' : `${completionRate.toFixed(2)}%`}</strong>
            </div>
          </div>
        `
      },
    },
    legend: { ...baseOption.legend, top: 0 },
    grid: { ...baseOption.grid, left: 100, right: 28 },
    xAxis: { type: 'value' as const, ...axisStyle },
    yAxis: {
      type: 'category' as const,
      data: categories,
      ...axisStyle,
      inverse: true,
      axisLabel: { ...axisStyle.axisLabel, width: 85, overflow: 'truncate' as const },
    },
    series: series.map((s, i) => ({
      ...s,
      type: 'bar' as const,
      barWidth: i === 0 ? '40%' : '40%',
      barGap: '-100%',
      z: i === 0 ? 2 : 1,
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: i === 0
          ? {
              type: 'linear' as const,
              x: 0, y: 0, x2: 1, y2: 0,
              colorStops: [
                { offset: 0, color: chartPalette[0] },
                { offset: 1, color: `${chartPalette[0]}55` },
              ],
            }
          : 'rgba(34,211,238,0.05)',
        shadowBlur: i === 0 ? 6 : 0,
        shadowColor: i === 0 ? 'rgba(34,211,238,0.12)' : 'transparent',
      },
    })),
  }

  return <ReactECharts ref={chartRef} option={option} notMerge style={{ height: resolvedHeightProp }} {...(isFluid ? { opts: { height: 'auto' } } : {})} />
}

export default HorizontalBarChart
