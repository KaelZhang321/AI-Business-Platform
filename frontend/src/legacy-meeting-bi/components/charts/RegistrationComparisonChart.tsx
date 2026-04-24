import React from 'react'
import ReactECharts from 'echarts-for-react'
import { axisStyle, baseOption, chartPalette } from './echarts-config'

interface RegistrationComparisonChartProps {
  categories: string[]
  levels: string[]
  registerSeries: number[][]
  arriveSeries: number[][]
  height?: number | string
}

const formatRegionLabel = (value: string) => {
  if (value.includes('大区')) return value.replace('大区', '\n大区')
  if (value.endsWith('BU')) return value.replace('BU', '\nBU')
  if (value.length >= 6) {
    const pivot = Math.ceil(value.length / 2)
    return `${value.slice(0, pivot)}\n${value.slice(pivot)}`
  }
  return value
}

const RegistrationComparisonChart: React.FC<RegistrationComparisonChartProps> = ({
  categories,
  levels,
  registerSeries,
  arriveSeries,
  height = 320,
}) => {
  const levelColors = levels.map((_, index) => chartPalette[index % chartPalette.length])
  const resolvedHeightProp: number | string = height

  const option = {
    ...baseOption,
    color: levelColors,
    legend: { show: false },
    grid: { ...baseOption.grid, left: 52, right: 16, top: 18, bottom: 62 },
    tooltip: {
      ...baseOption.tooltip,
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      formatter: (params: Array<{ dataIndex: number }>) => {
        const dataIndex = params[0]?.dataIndex ?? 0
        const region = categories[dataIndex] ?? ''
        const registerItems = levels
          .map((level, index) => ({
            color: levelColors[index],
            level,
            value: registerSeries[index]?.[dataIndex] ?? 0,
          }))
          .filter((item) => item.value > 0)
        const arriveItems = levels
          .map((level, index) => ({
            color: levelColors[index],
            level,
            value: arriveSeries[index]?.[dataIndex] ?? 0,
          }))
          .filter((item) => item.value > 0)
        const totalRegister = registerItems.reduce((sum, item) => sum + item.value, 0)
        const totalArrive = arriveItems.reduce((sum, item) => sum + item.value, 0)
        const arrivalRate = totalRegister > 0 ? ((totalArrive / totalRegister) * 100).toFixed(1) : '0.0'
        const renderItems = (items: Array<{ color: string; level: string; value: number }>, alpha: string) =>
          items.length > 0
            ? items.map((item) => `
                <div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:4px;">
                  <span style="display:flex;align-items:center;gap:6px;min-width:0;">
                    <span style="width:8px;height:8px;border-radius:999px;background:${item.color}${alpha};box-shadow:0 0 8px ${item.color}55;"></span>
                    <span>${item.level}</span>
                  </span>
                  <strong style="color:#E2E8F0;">${item.value}</strong>
                </div>
              `).join('')
            : '<div style="margin-top:4px;color:#64748B;">无</div>'

        return `
          <div style="min-width:220px;">
            <div style="font-weight:700;color:#E2E8F0;margin-bottom:8px;">${region}</div>
            <div style="padding:8px 0;border-top:1px solid rgba(34,211,238,0.08);">
              <div style="color:#94A3B8;font-size:11px;">报名分解</div>
              ${renderItems(registerItems, '66')}
            </div>
            <div style="padding:8px 0;border-top:1px solid rgba(34,211,238,0.08);">
              <div style="color:#94A3B8;font-size:11px;">抵达分解</div>
              ${renderItems(arriveItems, '')}
            </div>
            <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 12px;padding-top:8px;border-top:1px solid rgba(34,211,238,0.08);">
              <div><span style="color:#64748B;">总报名</span> <strong style="color:#22D3EE;">${totalRegister}</strong></div>
              <div><span style="color:#64748B;">总抵达</span> <strong style="color:#34D399;">${totalArrive}</strong></div>
              <div><span style="color:#64748B;">抵达率</span> <strong style="color:#FBBF24;">${arrivalRate}%</strong></div>
              <div><span style="color:#64748B;">差额</span> <strong style="color:#F87171;">${totalRegister - totalArrive}</strong></div>
            </div>
          </div>
        `
      },
    },
    xAxis: {
      type: 'category' as const,
      data: categories,
      ...axisStyle,
      axisLabel: {
        ...axisStyle.axisLabel,
        interval: 0,
        margin: 12,
        formatter: (value: string) => formatRegionLabel(value),
      },
    },
    yAxis: { type: 'value' as const, ...axisStyle },
    series: [
      ...levels.map((level, index) => ({
        name: `报名·${level}`,
        type: 'bar' as const,
        stack: '报名',
        data: registerSeries[index] ?? [],
        barWidth: 12,
        barGap: '30%',
        barCategoryGap: '45%',
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: `${levelColors[index]}66`,
          borderColor: `${levelColors[index]}AA`,
          borderWidth: 1,
        },
      })),
      ...levels.map((level, index) => ({
        name: `抵达·${level}`,
        type: 'bar' as const,
        stack: '抵达',
        data: arriveSeries[index] ?? [],
        barWidth: 12,
        barGap: '30%',
        barCategoryGap: '45%',
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: levelColors[index],
          shadowBlur: 10,
          shadowColor: `${levelColors[index]}35`,
        },
      })),
    ],
  }

  const isFluid = typeof resolvedHeightProp === 'string' && resolvedHeightProp === '100%'
  return <ReactECharts option={option} notMerge style={{ height: resolvedHeightProp }} {...(isFluid ? { opts: { height: 'auto' } } : {})} />
}

export default RegistrationComparisonChart
