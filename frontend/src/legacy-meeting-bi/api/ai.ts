import { apiClient as client, type ApiResponse } from './client';
import { apiBasePath } from '../utils/base-path'

export type ChartValue = string | number | null
export type ChartDatum = ChartValue | ({ name?: string; value?: ChartValue } & Record<string, unknown>)
export interface ChartSeries {
  name: string
  data: ChartDatum[]
  stack?: string
}

export interface ChartConfig {
  chart_type: 'pie' | 'bar' | 'grouped_bar' | 'horizontal_bar' | 'line' | 'none'
  categories: string[]
  series: ChartSeries[]
}

export type QueryCellValue = string | number | boolean | null
export type QueryRow = Record<string, QueryCellValue>

export interface AiQueryResponse {
  sql: string
  columns: string[]
  rows: QueryRow[]
  answer: string
  chart: ChartConfig | null
}

export const postAiQuery = (question: string) =>
  client.post<ApiResponse<AiQueryResponse>>('/api/v1/bi/ai/query', { question }).then(r => r.data.data)

export type SseEventType = 'sql' | 'data' | 'chart' | 'answer' | 'error'

export interface SseCallback {
  onSql?: (sql: string) => void
  onData?: (columns: string[], rows: QueryRow[]) => void
  onChart?: (chart: ChartConfig) => void
  onAnswer?: (answer: string) => void
  onError?: (message: string) => void
}

export async function streamAiQuery(question: string, callbacks: SseCallback, conversationId?: string) {
  const response = await fetch(`${apiBasePath}/api/v1/bi/ai/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, conversation_id: conversationId }),
  })

  if (!response.ok || !response.body) {
    callbacks.onError?.(`请求失败: ${response.status}`)
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        const raw = line.slice(5).trim()
        if (!raw || !currentEvent) continue
        try {
          const parsed = JSON.parse(raw) as {
            sql?: string
            columns?: string[]
            rows?: QueryRow[]
            chart?: ChartConfig
            answer?: string
            message?: string
          }
          switch (currentEvent as SseEventType) {
            case 'sql':
              callbacks.onSql?.(parsed.sql ?? '')
              break
            case 'data':
              callbacks.onData?.(parsed.columns ?? [], parsed.rows ?? [])
              break
            case 'chart':
              if (parsed.chart) {
                callbacks.onChart?.(parsed.chart)
              }
              break
            case 'answer':
              callbacks.onAnswer?.(parsed.answer ?? '')
              break
            case 'error':
              callbacks.onError?.(parsed.message ?? '未知错误')
              break
          }
        } catch {
          // 忽略解析错误
        }
        currentEvent = ''
      }
    }
  }
}
