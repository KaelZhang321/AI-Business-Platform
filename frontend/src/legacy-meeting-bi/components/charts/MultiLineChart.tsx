import React from 'react'
import ReactECharts from 'echarts-for-react'
import { baseOption, axisStyle, chartPalette } from './echarts-config'

interface MultiLineChartProps {
  categories: string[]
  series: { name: string; data: number[] }[]
  height?: number
}

const MultiLineChart: React.FC<MultiLineChartProps> = ({ categories, series, height = 350 }) => {
  const option = {
    ...baseOption,
    color: chartPalette,
    tooltip: { ...baseOption.tooltip, trigger: 'axis' as const },
    legend: { ...baseOption.legend, top: 0, itemWidth: 16, itemHeight: 3, itemGap: 18 },
    xAxis: {
      type: 'category' as const,
      data: categories,
      ...axisStyle,
      boundaryGap: false,
      axisLabel: { ...axisStyle.axisLabel, interval: 0, rotate: categories.length > 10 ? 30 : 0 },
    },
    yAxis: { type: 'value' as const, ...axisStyle },
    series: series.map((s, i) => ({
      ...s,
      type: 'line' as const,
      smooth: 0.4,
      symbolSize: 5,
      symbol: 'circle',
      lineStyle: {
        width: 2.5,
        shadowBlur: 8,
        shadowColor: `${chartPalette[i % chartPalette.length]}25`,
      },
      areaStyle: {
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: `${chartPalette[i % chartPalette.length]}18` },
            { offset: 1, color: `${chartPalette[i % chartPalette.length]}02` },
          ],
        },
      },
      emphasis: { focus: 'series' as const },
    })),
  }

  return <ReactECharts option={option} notMerge style={{ height }} />
}

export default MultiLineChart
