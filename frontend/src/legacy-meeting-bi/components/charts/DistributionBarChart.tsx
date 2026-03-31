import React, { useEffect, useRef } from 'react'
import ReactECharts from 'echarts-for-react'
import { axisStyle, baseOption, chartPalette } from './echarts-config'
import type { PieSlice } from '../../api/customer'

interface DistributionBarChartProps {
  data: PieSlice[]
  height?: number | string
  seriesName?: string
}

const DistributionBarChart: React.FC<DistributionBarChartProps> = ({
  data,
  height = 280,
  seriesName = '客户数',
}) => {
  const chartRef = useRef<ReactECharts>(null)
  const resolvedHeightProp: number | string = height
  const isFluid = typeof resolvedHeightProp === 'string' && resolvedHeightProp === '100%'
  const sortedData = [...data].sort((a, b) => b.value - a.value)
  const categories = sortedData.map((item) => item.name)
  const values = sortedData.map((item) => item.value)
  const percentages = sortedData.map((item) => item.percentage)
  const maxValue = Math.max(...values, 0)
  const resolvedHeight = typeof resolvedHeightProp === 'number'
    ? Math.max(resolvedHeightProp, sortedData.length * 28 + 96)
    : resolvedHeightProp

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
    color: [chartPalette[0]],
    legend: { show: false },
    tooltip: {
      ...baseOption.tooltip,
      trigger: 'item' as const,
      axisPointer: { show: false },
      appendToBody: true,
      confine: true,
      transitionDuration: 0.12,
      extraCssText: 'backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);box-shadow:0 10px 24px rgba(0,0,0,0.34),0 0 10px rgba(34,211,238,0.08);border-radius:12px;padding:9px 11px;',
      position: (
        point: number[],
        _params: unknown,
        _dom: unknown,
        _rect: unknown,
        size: { viewSize: number[]; contentSize: number[] },
      ) => {
        const [px, py] = point
        const [viewW, viewH] = size.viewSize
        const [boxW, boxH] = size.contentSize

        let left = px + 14
        if (left + boxW > viewW - 8) left = px - boxW - 14
        left = Math.max(8, Math.min(left, viewW - boxW - 8))

        let top = py - boxH / 2
        top = Math.max(8, Math.min(top, viewH - boxH - 8))

        return [left, top]
      },
      formatter: (params: { dataIndex?: number; color?: string }) => {
        const item = sortedData[params?.dataIndex ?? 0]
        if (!item) return ''
        return `
          <div style="min-width:134px;">
            <div style="font-weight:700;color:#F8FAFC;margin-bottom:8px;font-size:13px;">${item.name}</div>
            <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:2px;">
              <span style="display:flex;align-items:center;gap:6px;">
                <span style="width:7px;height:7px;border-radius:999px;background:${params?.color};box-shadow:0 0 7px ${params?.color}55;"></span>
                <span style="color:#94A3B8;">${seriesName}</span>
              </span>
              <strong style="color:#E2E8F0;font-size:12px;">${item.value.toLocaleString()}</strong>
            </div>
            <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:8px;padding-top:8px;border-top:1px solid rgba(34,211,238,0.08);">
              <span style="color:#94A3B8;">占比</span>
              <strong style="color:#22D3EE;font-size:12px;">${item.percentage.toFixed(2)}%</strong>
            </div>
          </div>
        `
      },
    },
    grid: {
      ...baseOption.grid,
      left: 132,
      right: 92,
      top: 6,
      bottom: 16,
      containLabel: false,
    },
    xAxis: {
      type: 'value' as const,
      ...axisStyle,
      splitNumber: 4,
      max: maxValue > 0 ? Math.ceil(maxValue * 1.12) : undefined,
      axisLine: { show: false },
      axisLabel: {
        ...axisStyle.axisLabel,
        show: false,
      },
    },
    yAxis: {
      type: 'category' as const,
      data: categories,
      ...axisStyle,
      inverse: true,
      axisLabel: {
        ...axisStyle.axisLabel,
        width: 136,
        overflow: 'truncate' as const,
        margin: 18,
        lineHeight: 18,
        fontSize: 12,
        color: '#A8B4CC',
      },
    },
    series: [
      {
        name: seriesName,
        type: 'bar' as const,
        data: values,
        showBackground: true,
        backgroundStyle: {
          color: 'rgba(148, 163, 184, 0.08)',
          borderRadius: 999,
        },
        barWidth: 14,
        barCategoryGap: '38%',
        label: {
          show: true,
          position: 'right' as const,
          distance: 12,
          color: '#C7D2E4',
          fontSize: 11,
          fontWeight: 500,
          formatter: ({ dataIndex, value }: { dataIndex: number; value: number }) => {
            const percentage = percentages[dataIndex]
            return percentage == null ? value.toLocaleString() : `{value|${value.toLocaleString()}}  {percent|${percentage.toFixed(1)}%}`
          },
          rich: {
            value: {
              color: '#E2E8F0',
              fontSize: 11,
              fontWeight: 600,
            },
            percent: {
              color: '#7DD3FC',
              fontSize: 10,
              fontWeight: 500,
              backgroundColor: 'rgba(34,211,238,0.10)',
              borderRadius: 999,
              padding: [3, 6],
            },
          },
        },
        itemStyle: {
          borderRadius: 999,
          color: {
            type: 'linear' as const,
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: chartPalette[0] },
              { offset: 0.55, color: '#38D7F0' },
              { offset: 1, color: `${chartPalette[0]}66` },
            ],
          },
          shadowBlur: 8,
          shadowColor: `${chartPalette[0]}22`,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 16,
            shadowColor: `${chartPalette[0]}35`,
          },
        },
      },
    ],
  }

  return <ReactECharts ref={chartRef} option={option} notMerge style={{ height: resolvedHeight }} {...(isFluid ? { opts: { height: 'auto' } } : {})} />
}

export default DistributionBarChart
