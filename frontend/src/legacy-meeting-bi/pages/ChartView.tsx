import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ReactECharts from 'echarts-for-react'
import { baseOption, axisStyle, chartPalette } from '../components/charts/echarts-config'
import type { ChartConfig } from '../api/ai'
import { theme } from '../styles/theme'
import { apiBasePath } from '../utils/base-path'

type ChartData = ChartConfig

const ChartView: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const [data, setData] = useState<ChartData | null>(null)
  const [error, setError] = useState<string>('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    fetch(`${apiBasePath}/v1/chart/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status === 404 ? '图表不存在或已过期' : '加载失败')
        return r.json()
      })
      .then((res) => setData(res.data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <div style={styles.loadingText}>加载中...</div>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <div style={styles.errorText}>{error || '图表数据为空'}</div>
        </div>
      </div>
    )
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.header}>
          <div style={styles.badge}>BI 智能助手</div>
          <h2 style={styles.title}>{getChartTitle(data.chart_type)}</h2>
        </div>
        <div style={styles.chartWrap}>
          <ReactECharts option={buildOption(data)} notMerge style={{ height: '100%', width: '100%' }} />
        </div>
      </div>
    </div>
  )
}

function getChartTitle(chartType: ChartData['chart_type']): string {
  const map: Record<string, string> = {
    pie: '饼图', bar: '柱状图', horizontal_bar: '条形图',
    grouped_bar: '分组柱状图', line: '折线图',
  }
  return `查询结果 — ${map[chartType] || '图表'}`
}

function buildOption(data: ChartData) {
  const { chart_type, categories, series } = data

  if (chart_type === 'pie') {
    const pieData = categories.map((name, i) => ({
      name,
      value: series[0]?.data[i] ?? 0,
    }))
    return {
      ...baseOption,
      color: chartPalette,
      tooltip: { ...baseOption.tooltip, trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
      legend: { ...baseOption.legend, orient: 'horizontal' as const, right: 0, bottom: 10, icon: 'circle', itemWidth: 8, itemHeight: 8 },
      series: [{
        type: 'pie' as const,
        radius: ['42%', '68%'],
        center: ['50%', '45%'],
        data: pieData,
        label: { show: true, formatter: '{d}%', color: '#8896B3', fontSize: 11 },
        labelLine: { lineStyle: { color: 'rgba(136,150,179,0.2)' } },
        itemStyle: { borderColor: 'transparent', shadowBlur: 8, shadowColor: 'rgba(63,101,224,0.16)' },
        emphasis: { scale: true, scaleSize: 4, itemStyle: { shadowBlur: 20, shadowColor: 'rgba(34,211,238,0.3)' } },
      }],
    }
  }

  if (chart_type === 'horizontal_bar') {
    return {
      ...baseOption,
      color: chartPalette,
      tooltip: { ...baseOption.tooltip, trigger: 'axis' as const },
      legend: { ...baseOption.legend, top: 0 },
      grid: { ...baseOption.grid, left: 100, right: 28 },
      xAxis: { type: 'value' as const, ...axisStyle },
      yAxis: { type: 'category' as const, data: categories, ...axisStyle, inverse: true },
      series: series.map((s, i) => ({
        ...s, type: 'bar' as const, barWidth: '50%',
        itemStyle: { borderRadius: [0, 4, 4, 0], color: chartPalette[i % chartPalette.length] },
      })),
    }
  }

  if (chart_type === 'line') {
    return {
      ...baseOption,
      color: chartPalette,
      tooltip: { ...baseOption.tooltip, trigger: 'axis' as const },
      legend: { ...baseOption.legend, top: 0 },
      xAxis: { type: 'category' as const, data: categories, ...axisStyle, boundaryGap: false },
      yAxis: { type: 'value' as const, ...axisStyle },
      series: series.map((s, i) => ({
        ...s, type: 'line' as const, smooth: 0.4, symbolSize: 5, symbol: 'circle',
        lineStyle: { width: 2.5, shadowBlur: 8, shadowColor: `${chartPalette[i % chartPalette.length]}25` },
        areaStyle: {
          color: { type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1, colorStops: [
            { offset: 0, color: `${chartPalette[i % chartPalette.length]}18` },
            { offset: 1, color: `${chartPalette[i % chartPalette.length]}02` },
          ]},
        },
      })),
    }
  }

  // bar / grouped_bar
  const isGrouped = chart_type === 'grouped_bar'
  return {
    ...baseOption,
    color: chartPalette,
    tooltip: { ...baseOption.tooltip, trigger: 'axis' as const },
    legend: { ...baseOption.legend, top: 0, ...(series.length > 6 ? { type: 'scroll' as const } : {}) },
    xAxis: { type: 'category' as const, data: categories, ...axisStyle, axisLabel: { ...axisStyle.axisLabel, rotate: categories.length > 8 ? 30 : 0, interval: 0 } },
    yAxis: { type: 'value' as const, ...axisStyle },
    series: series.map((s) => ({
      ...s, type: 'bar' as const,
      stack: isGrouped ? undefined : s.stack || 'total',
      barWidth: isGrouped ? '22%' : '35%',
      ...(isGrouped ? { barGap: '30%' } : {}),
      itemStyle: { borderRadius: [4, 4, 0, 0], shadowBlur: 4, shadowColor: 'rgba(0,0,0,0.2)' },
    })),
  }
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: '100vh',
    background: `linear-gradient(160deg, ${theme.colors.bgPage} 0%, #0a1d45 50%, ${theme.colors.bgPage} 100%)`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    width: '100%',
    maxWidth: 800,
    background: theme.colors.bgCard,
    borderRadius: theme.cardRadius,
    border: `1px solid ${theme.colors.borderSubtle}`,
    boxShadow: theme.shadows.card,
    overflow: 'hidden',
  },
  header: {
    padding: '20px 24px 0',
  },
  badge: {
    display: 'inline-block',
    fontSize: 11,
    color: theme.colors.accentCyan,
    background: 'rgba(121, 231, 255, 0.1)',
    border: `1px solid rgba(121, 231, 255, 0.2)`,
    borderRadius: 4,
    padding: '2px 8px',
    marginBottom: 8,
  },
  title: {
    margin: 0,
    fontSize: 18,
    fontWeight: 600,
    color: theme.colors.textPrimary,
    fontFamily: theme.fontFamily,
  },
  chartWrap: {
    height: 420,
    padding: '16px 16px 24px',
  },
  loadingText: {
    padding: 60,
    textAlign: 'center' as const,
    color: theme.colors.textSecondary,
    fontSize: 15,
  },
  errorText: {
    padding: 60,
    textAlign: 'center' as const,
    color: theme.colors.accentRed,
    fontSize: 15,
  },
}

export default ChartView
