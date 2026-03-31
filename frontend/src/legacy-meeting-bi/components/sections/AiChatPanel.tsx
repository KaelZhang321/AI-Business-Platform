import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactECharts from 'echarts-for-react'
import { Table, Input, Button } from 'antd'
import { SearchOutlined, DownloadOutlined, DeleteOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { theme } from '../../styles/theme'
import { streamAiQuery, type AiQueryResponse, type ChartConfig, type QueryCellValue, type QueryRow } from '../../api/ai'

const PALETTE = theme.chartPalette
const STORAGE_KEY = 'ai-chat-history'

/* ========== 颜色方案 ========== */
interface ColorScheme {
  panelBg: string; panelBorder: string; panelShadow: string; overlayBg: string
  headerBorder: string; iconBg: string; iconBorder: string; iconStroke: string
  titleColor: string; subtitleColor: string; btnBorder: string; btnColor: string
  emptyTextColor: string
  exampleBorder: string; exampleBg: string; exampleBorderHover: string; exampleBgHover: string; exampleColor: string
  userBubbleBg: string; userBubbleBorder: string; userTextColor: string
  loadingDotColor: string; loadingTextColor: string
  aiBubbleBg: string; aiBubbleBorder: string; aiTextColor: string
  chartBorderColor: string; chartBg: string
  sqlLinkColor: string; sqlBg: string; sqlBorder: string; sqlTextColor: string
  inputAreaBorder: string; inputBoxBorder: string; inputBoxBg: string; inputTextColor: string
  sendBtnBg: string; sendBtnBgDisabled: string; sendBtnColor: string; sendBtnColorDisabled: string
  errorBorder: string
  tooltipBg: string; tooltipBorder: string; tooltipTextColor: string
  chartTextColor: string; axisLineColor: string; axisLabelColor: string; splitLineColor: string
  pieBorderColor: string; pieEmphasisShadow: string; searchIconColor: string
}

const darkScheme: ColorScheme = {
  panelBg: 'linear-gradient(180deg, #050e22 0%, #020a18 100%)',
  panelBorder: `${theme.colors.accentCyan}20`,
  panelShadow: '-12px 0 48px rgba(0,0,0,0.5)',
  overlayBg: 'rgba(0,0,0,0.5)',
  headerBorder: `${theme.colors.accentCyan}12`,
  iconBg: `${theme.colors.accentCyan}10`,
  iconBorder: `${theme.colors.accentCyan}25`,
  iconStroke: theme.colors.accentCyan,
  titleColor: theme.colors.textPrimary,
  subtitleColor: theme.colors.textSecondary,
  btnBorder: theme.colors.borderSubtle,
  btnColor: theme.colors.textSecondary,
  emptyTextColor: theme.colors.textSecondary,
  exampleBorder: `${theme.colors.accentCyan}18`,
  exampleBg: `${theme.colors.accentCyan}06`,
  exampleBorderHover: `${theme.colors.accentCyan}40`,
  exampleBgHover: `${theme.colors.accentCyan}12`,
  exampleColor: theme.colors.accentCyan,
  userBubbleBg: `${theme.colors.accentCyan}12`,
  userBubbleBorder: `${theme.colors.accentCyan}20`,
  userTextColor: theme.colors.textPrimary,
  loadingDotColor: theme.colors.accentCyan,
  loadingTextColor: theme.colors.textSecondary,
  aiBubbleBg: 'rgba(6,16,40,0.8)',
  aiBubbleBorder: theme.colors.borderSubtle,
  aiTextColor: theme.colors.textPrimary,
  chartBorderColor: theme.colors.borderSubtle,
  chartBg: 'rgba(0,0,0,0.12)',
  sqlLinkColor: theme.colors.accentCyan,
  sqlBg: 'rgba(0,0,0,0.25)',
  sqlBorder: theme.colors.borderSubtle,
  sqlTextColor: theme.colors.accentCyan,
  inputAreaBorder: `${theme.colors.accentCyan}08`,
  inputBoxBorder: `${theme.colors.accentCyan}18`,
  inputBoxBg: 'rgba(6,16,40,0.6)',
  inputTextColor: theme.colors.textPrimary,
  sendBtnBg: theme.colors.accentCyan,
  sendBtnBgDisabled: `${theme.colors.accentCyan}12`,
  sendBtnColor: '#020a18',
  sendBtnColorDisabled: theme.colors.textSecondary,
  errorBorder: theme.colors.accentRed + '30',
  // chart tooltip
  tooltipBg: 'rgba(4,10,28,0.96)',
  tooltipBorder: 'rgba(34,211,238,0.15)',
  tooltipTextColor: '#E8ECF4',
  chartTextColor: '#8896B3',
  axisLineColor: 'rgba(34,211,238,0.06)',
  axisLabelColor: '#6B7A99',
  splitLineColor: 'rgba(34,211,238,0.03)',
  pieBorderColor: 'rgba(2,10,24,0.9)',
  pieEmphasisShadow: 'rgba(34,211,238,0.25)',
  searchIconColor: theme.colors.textSecondary,
}

const lightScheme: ColorScheme = {
  panelBg: '#FFFFFF',
  panelBorder: '#E5E7EB',
  panelShadow: '-8px 0 32px rgba(0,0,0,0.1)',
  overlayBg: 'rgba(0,0,0,0.3)',
  headerBorder: '#E5E7EB',
  iconBg: 'rgba(59,130,246,0.08)',
  iconBorder: 'rgba(59,130,246,0.2)',
  iconStroke: '#3B82F6',
  titleColor: '#1A1D2E',
  subtitleColor: '#6B7280',
  btnBorder: '#E5E7EB',
  btnColor: '#6B7280',
  emptyTextColor: '#6B7280',
  exampleBorder: 'rgba(59,130,246,0.15)',
  exampleBg: 'rgba(59,130,246,0.04)',
  exampleBorderHover: 'rgba(59,130,246,0.3)',
  exampleBgHover: 'rgba(59,130,246,0.08)',
  exampleColor: '#3B82F6',
  userBubbleBg: 'rgba(59,130,246,0.08)',
  userBubbleBorder: 'rgba(59,130,246,0.15)',
  userTextColor: '#1A1D2E',
  loadingDotColor: '#3B82F6',
  loadingTextColor: '#6B7280',
  aiBubbleBg: '#F8F9FB',
  aiBubbleBorder: '#E5E7EB',
  aiTextColor: '#1A1D2E',
  chartBorderColor: '#E5E7EB',
  chartBg: '#F8F9FB',
  sqlLinkColor: '#3B82F6',
  sqlBg: '#F2F4F8',
  sqlBorder: '#E5E7EB',
  sqlTextColor: '#3B82F6',
  inputAreaBorder: '#E5E7EB',
  inputBoxBorder: '#E5E7EB',
  inputBoxBg: '#F8F9FB',
  inputTextColor: '#1A1D2E',
  sendBtnBg: '#3B82F6',
  sendBtnBgDisabled: 'rgba(59,130,246,0.1)',
  sendBtnColor: '#FFFFFF',
  sendBtnColorDisabled: '#9CA3AF',
  errorBorder: '#FCA5A5',
  // chart tooltip
  tooltipBg: 'rgba(255,255,255,0.96)',
  tooltipBorder: '#E5E7EB',
  tooltipTextColor: '#1A1D2E',
  chartTextColor: '#6B7280',
  axisLineColor: '#E5E7EB',
  axisLabelColor: '#6B7280',
  splitLineColor: '#F3F4F6',
  pieBorderColor: '#FFFFFF',
  pieEmphasisShadow: 'rgba(59,130,246,0.2)',
  searchIconColor: '#9CA3AF',
}

interface ChatMessage {
  id: number
  role: 'user' | 'ai'
  content: string
  data?: AiQueryResponse
  loading?: boolean
  error?: boolean
  stage?: string
}

function loadHistory(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as ChatMessage[]
    return parsed.map((m) => ({ ...m, loading: false, stage: undefined }))
  } catch {
    return []
  }
}

const EXAMPLES = [
  '各大区报名人数是多少？',
  '新老客户比例是多少？',
  '各区域目标完成情况如何？',
  '客户金额等级分布是什么？',
  '各场景参与人数是多少？',
  '总成交金额是多少？',
]

/* ========== 图表渲染 ========== */
function buildChartOption(chart: ChartConfig, c: ColorScheme) {
  const base = {
    backgroundColor: 'transparent',
    color: PALETTE,
    textStyle: { fontFamily: theme.fontFamily, color: c.chartTextColor },
    tooltip: {
      backgroundColor: c.tooltipBg,
      borderColor: c.tooltipBorder,
      textStyle: { color: c.tooltipTextColor, fontSize: 11 },
      extraCssText: 'backdrop-filter:blur(16px);border-radius:8px;',
    },
    grid: { left: 50, right: 16, top: 30, bottom: 30 },
  }

  if (chart.chart_type === 'pie') {
    return {
      ...base,
      tooltip: { ...base.tooltip, trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { orient: 'vertical', right: 4, top: 'middle', textStyle: { color: c.chartTextColor, fontSize: 10 }, icon: 'circle', itemWidth: 8, itemHeight: 8, itemGap: 10 },
      series: [{ type: 'pie', radius: ['35%', '60%'], center: ['40%', '50%'], data: chart.series[0]?.data || [], label: { show: true, formatter: '{d}%', color: c.chartTextColor, fontSize: 10 }, labelLine: { lineStyle: { color: c.splitLineColor } }, itemStyle: { borderColor: c.pieBorderColor, borderWidth: 2 }, emphasis: { scale: true, scaleSize: 4, itemStyle: { shadowBlur: 14, shadowColor: c.pieEmphasisShadow } } }],
    }
  }

  const axisStyle = { axisLine: { lineStyle: { color: c.axisLineColor } }, axisTick: { show: false }, axisLabel: { color: c.axisLabelColor, fontSize: 9 }, splitLine: { lineStyle: { color: c.splitLineColor, type: 'dashed' as const } } }

  if (chart.chart_type === 'horizontal_bar') {
    return {
      ...base,
      grid: { left: 90, right: 16, top: 20, bottom: 20 },
      tooltip: { ...base.tooltip, trigger: 'axis' },
      xAxis: { type: 'value', ...axisStyle },
      yAxis: { type: 'category', data: chart.categories, inverse: true, ...axisStyle, axisLabel: { ...axisStyle.axisLabel, width: 80, overflow: 'truncate' } },
      series: chart.series.map((s, i) => ({ ...s, type: 'bar', barWidth: '50%', itemStyle: { borderRadius: [0, 4, 4, 0], color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: PALETTE[i % PALETTE.length] }, { offset: 1, color: `${PALETTE[i % PALETTE.length]}55` }] } } })),
    }
  }

  if (chart.chart_type === 'line') {
    return {
      ...base,
      tooltip: { ...base.tooltip, trigger: 'axis' },
      legend: { textStyle: { color: c.chartTextColor, fontSize: 10 }, top: 0 },
      xAxis: { type: 'category', data: chart.categories, boundaryGap: false, ...axisStyle },
      yAxis: { type: 'value', ...axisStyle },
      series: chart.series.map((s, i) => ({ ...s, type: 'line', smooth: 0.4, symbolSize: 4, lineStyle: { width: 2, shadowBlur: 6, shadowColor: `${PALETTE[i % PALETTE.length]}25` }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: `${PALETTE[i % PALETTE.length]}18` }, { offset: 1, color: `${PALETTE[i % PALETTE.length]}02` }] } } })),
    }
  }

  // bar / grouped_bar
  return {
    ...base,
    tooltip: { ...base.tooltip, trigger: 'axis' },
    legend: chart.series.length > 1 ? { textStyle: { color: c.chartTextColor, fontSize: 10 }, top: 0, itemWidth: 12, itemHeight: 3 } : undefined,
    xAxis: { type: 'category', data: chart.categories, ...axisStyle, axisLabel: { ...axisStyle.axisLabel, rotate: chart.categories.length > 6 ? 25 : 0, interval: 0 } },
    yAxis: { type: 'value', ...axisStyle },
    series: chart.series.map((s, i) => ({ ...s, type: 'bar', barWidth: chart.series.length > 1 ? '22%' : '40%', barGap: '30%', itemStyle: { borderRadius: [3, 3, 0, 0], color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: PALETTE[i % PALETTE.length] }, { offset: 1, color: `${PALETTE[i % PALETTE.length]}55` }] } } })),
  }
}

function AiChart({ chart, colors }: { chart: ChartConfig; colors: ColorScheme }) {
  const option = useMemo(() => buildChartOption(chart, colors), [chart, colors])
  const h = chart.chart_type === 'horizontal_bar' ? Math.max(200, chart.categories.length * 32) : chart.chart_type === 'pie' ? 240 : 260
  return (
    <div style={{ marginTop: 12, borderRadius: 8, border: `1px solid ${colors.chartBorderColor}`, overflow: 'hidden', background: colors.chartBg }}>
      <ReactECharts option={option} style={{ height: h }} />
    </div>
  )
}

/* ========== 数据表格 ========== */
function DataTable({ columns, rows, colors }: { columns: string[]; rows: QueryRow[]; colors: ColorScheme }) {
  const [search, setSearch] = useState('')

  const filteredRows = useMemo(() => {
    if (!search.trim()) return rows
    const keyword = search.trim().toLowerCase()
    return rows.filter((row) =>
      columns.some((col) => String(row[col] ?? '').toLowerCase().includes(keyword))
    )
  }, [rows, columns, search])

  const tableColumns: ColumnsType<QueryRow> = useMemo(
    () =>
      columns.map((col) => ({
        title: col,
        dataIndex: col,
        key: col,
        ellipsis: true,
        sorter: (a: QueryRow, b: QueryRow) => {
          const va = a[col]
          const vb = b[col]
          if (typeof va === 'number' && typeof vb === 'number') return va - vb
          return String(va ?? '').localeCompare(String(vb ?? ''))
        },
        render: (value: QueryCellValue) => (value == null ? '-' : String(value)),
      })),
    [columns]
  )

  const exportCsv = useCallback(() => {
    const header = columns.join(',')
    const body = rows.map((row) => columns.map((c) => `"${String(row[c] ?? '').replace(/"/g, '""')}"`).join(',')).join('\n')
    const csv = '\uFEFF' + header + '\n' + body
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `data_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [columns, rows])

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <Input.Search
          placeholder="搜索数据..."
          size="small"
          allowClear
          prefix={<SearchOutlined style={{ color: colors.searchIconColor }} />}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1 }}
        />
        <Button size="small" icon={<DownloadOutlined />} onClick={exportCsv}>
          导出 CSV
        </Button>
      </div>
      <Table
        columns={tableColumns}
        dataSource={filteredRows}
        rowKey={(_, i) => String(i)}
        size="small"
        scroll={{ y: 240 }}
        pagination={filteredRows.length > 50 ? { pageSize: 50, size: 'small' } : false}
      />
    </div>
  )
}

/* ========== 面板 ========== */
const AiChatPanel: React.FC<{ open: boolean; onClose: () => void; light?: boolean }> = ({ open, onClose, light }) => {
  const c = light ? lightScheme : darkScheme
  const [messages, setMessages] = useState<ChatMessage[]>(loadHistory)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const conversationIdRef = useRef(crypto.randomUUID())

  useEffect(() => {
    const toSave = messages.filter((m) => !m.loading)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
  }, [messages])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => { if (open) inputRef.current?.focus() }, [open])

  const clearHistory = () => {
    setMessages([])
    localStorage.removeItem(STORAGE_KEY)
    conversationIdRef.current = crypto.randomUUID()
  }

  const sendQuery = async (question: string) => {
    if (!question.trim() || loading) return
    const userMsg: ChatMessage = { id: Date.now(), role: 'user', content: question }
    const aiMsgId = Date.now() + 1
    const aiMsg: ChatMessage = { id: aiMsgId, role: 'ai', content: '', loading: true, stage: '正在生成 SQL...' }
    setMessages((p) => [...p, userMsg, aiMsg])
    setInput('')
    setLoading(true)

    const partial: Partial<AiQueryResponse> = { sql: '', columns: [], rows: [], answer: '', chart: null }

    const updateAiMsg = (updates: Partial<ChatMessage>) => {
      setMessages((p) =>
        p.map((m) => (m.id === aiMsgId ? { ...m, ...updates } : m))
      )
    }

    try {
      await streamAiQuery(question, {
        onSql: (sql) => {
          partial.sql = sql
          updateAiMsg({ stage: '正在查询数据...', data: { ...partial } as AiQueryResponse })
        },
        onData: (columns, rows) => {
          partial.columns = columns
          partial.rows = rows
          updateAiMsg({ stage: '正在分析结果...', data: { ...partial } as AiQueryResponse })
        },
        onChart: (chart) => {
          partial.chart = chart
          updateAiMsg({ stage: '正在生成回答...', data: { ...partial } as AiQueryResponse })
        },
        onAnswer: (answer) => {
          partial.answer = answer
          updateAiMsg({ content: answer, data: { ...partial } as AiQueryResponse, loading: false, stage: undefined })
        },
        onError: (message) => {
          updateAiMsg({ content: `查询失败: ${message}`, loading: false, error: true, stage: undefined })
        },
      }, conversationIdRef.current)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '网络错误'
      updateAiMsg({ content: `查询失败: ${message}`, loading: false, error: true, stage: undefined })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendQuery(input) } }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} style={{ position: 'fixed', inset: 0, background: c.overlayBg, backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)', zIndex: 999 }} />
          <motion.div
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 300 }}
            style={{
              position: 'fixed', top: 0, right: 0, bottom: 0, width: window.innerWidth <= 768 ? '100vw' : 560,
              background: c.panelBg,
              borderLeft: `1px solid ${c.panelBorder}`,
              zIndex: 1000,
              display: 'flex', flexDirection: 'column',
              boxShadow: c.panelShadow,
            }}
          >
            {/* 头部 */}
            <div style={{ padding: '18px 22px', borderBottom: `1px solid ${c.headerBorder}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 34, height: 34, borderRadius: 8,
                  background: c.iconBg,
                  border: `1px solid ${c.iconBorder}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={c.iconStroke} strokeWidth="2"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/><path d="M18 14a6 6 0 0 1-12 0"/><path d="M12 18v4"/><path d="M8 22h8"/></svg>
                </div>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: c.titleColor }}>知微AI（数据分析）</div>
                  <div style={{ fontSize: 11, color: c.subtitleColor, fontFamily: theme.fontMono }}>Vanna.ai + DeepSeek-v3</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button onClick={clearHistory} title="清空对话" style={{ width: 30, height: 30, borderRadius: 6, border: `1px solid ${c.btnBorder}`, background: 'transparent', color: c.btnColor, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, transition: 'all 0.2s' }}>
                  <DeleteOutlined />
                </button>
                <button onClick={onClose} style={{ width: 30, height: 30, borderRadius: 6, border: `1px solid ${c.btnBorder}`, background: 'transparent', color: c.btnColor, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, transition: 'all 0.2s' }}>&times;</button>
              </div>
            </div>

            {/* 消息 */}
            <div style={{ flex: 1, overflow: 'auto', padding: '18px 22px' }}>
              {messages.length === 0 && (
                <div style={{ textAlign: 'center', padding: '48px 0' }}>
                  <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke={c.iconStroke} strokeWidth="1.5" style={{ opacity: 0.2, marginBottom: 20 }}><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/><path d="M18 14a6 6 0 0 1-12 0"/><path d="M12 18v4"/><path d="M8 22h8"/></svg>
                  <div style={{ fontSize: 14, color: c.emptyTextColor, marginBottom: 24, lineHeight: 1.6 }}>用自然语言查询数据库，自动生成图表</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
                    {EXAMPLES.map((q) => (
                      <button key={q} onClick={() => sendQuery(q)} style={{ padding: '7px 14px', borderRadius: 6, border: `1px solid ${c.exampleBorder}`, background: c.exampleBg, color: c.exampleColor, fontSize: 12, cursor: 'pointer', fontFamily: theme.fontFamily, transition: 'all 0.2s' }}
                        onMouseEnter={(e) => { e.currentTarget.style.borderColor = c.exampleBorderHover; e.currentTarget.style.background = c.exampleBgHover }}
                        onMouseLeave={(e) => { e.currentTarget.style.borderColor = c.exampleBorder; e.currentTarget.style.background = c.exampleBg }}
                      >{q}</button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg) => (
                <div key={msg.id} style={{ marginBottom: 18 }}>
                  {msg.role === 'user' ? (
                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      <div style={{
                        maxWidth: '80%',
                        padding: '10px 16px',
                        borderRadius: '10px 2px 10px 10px',
                        background: c.userBubbleBg,
                        border: `1px solid ${c.userBubbleBorder}`,
                        fontSize: 13,
                        color: c.userTextColor,
                        lineHeight: 1.6,
                      }}>{msg.content}</div>
                    </div>
                  ) : msg.loading ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0' }}>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {[0, 1, 2].map((i) => <motion.div key={i} animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }} style={{ width: 6, height: 6, borderRadius: '50%', background: c.loadingDotColor }} />)}
                      </div>
                      <span style={{ fontSize: 12, color: c.loadingTextColor }}>{msg.stage || '正在分析并生成图表...'}</span>
                    </div>
                  ) : (
                    <div style={{
                      padding: '14px 18px',
                      borderRadius: '2px 10px 10px 10px',
                      background: c.aiBubbleBg,
                      border: `1px solid ${msg.error ? c.errorBorder : c.aiBubbleBorder}`,
                    }}>
                      {/* 回答 */}
                      <div style={{ fontSize: 13, color: c.aiTextColor, lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>{msg.content}</div>

                      {/* 图表 */}
                      {msg.data?.chart && msg.data.chart.chart_type !== 'none' && <AiChart chart={msg.data.chart} colors={c} />}

                      {/* SQL */}
                      {msg.data?.sql && (
                        <details style={{ marginTop: 12 }}>
                          <summary style={{ fontSize: 11, color: c.sqlLinkColor, cursor: 'pointer', fontFamily: theme.fontMono, userSelect: 'none', opacity: 0.8 }}>SQL 查询</summary>
                          <pre style={{ marginTop: 8, padding: 10, borderRadius: 6, background: c.sqlBg, border: `1px solid ${c.sqlBorder}`, fontSize: 11, color: c.sqlTextColor, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontFamily: theme.fontMono, lineHeight: 1.6 }}>{msg.data.sql}</pre>
                        </details>
                      )}

                      {/* 数据表 */}
                      {msg.data && msg.data.rows.length > 0 && (
                        <details style={{ marginTop: 8 }}>
                          <summary style={{ fontSize: 11, color: c.sqlLinkColor, cursor: 'pointer', fontFamily: theme.fontMono, userSelect: 'none', opacity: 0.8 }}>原始数据 ({msg.data.rows.length} 行)</summary>
                          <DataTable columns={msg.data.columns} rows={msg.data.rows} colors={c} />
                        </details>
                      )}
                    </div>
                  )}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            {/* 输入 */}
            <div style={{ padding: '14px 22px 18px', borderTop: `1px solid ${c.inputAreaBorder}` }}>
              <div style={{
                display: 'flex', gap: 10,
                padding: '10px 14px',
                borderRadius: 10,
                border: `1px solid ${c.inputBoxBorder}`,
                background: c.inputBoxBg,
                transition: 'border-color 0.2s',
              }}>
                <input ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="输入问题，自动生成图表..." disabled={loading}
                  style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: c.inputTextColor, fontSize: 13, fontFamily: theme.fontFamily, lineHeight: 1.5 }} />
                <button onClick={() => sendQuery(input)} disabled={loading || !input.trim()}
                  style={{
                    width: 34, height: 34, borderRadius: 8, border: 'none',
                    background: loading || !input.trim() ? c.sendBtnBgDisabled : c.sendBtnBg,
                    color: loading || !input.trim() ? c.sendBtnColorDisabled : c.sendBtnColor,
                    cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 0.2s',
                  }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4z"/></svg>
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

export default AiChatPanel
