import type { UISpec } from '../components/dynamic-ui/catalog'
export type { UISpec }

// 意图类型 — 对应文档 3.1 意图分类
export type IntentType = 'chat' | 'knowledge' | 'data_query' | 'task_operation'

// 对话消息
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  intent?: IntentType
  uiSpec?: UISpec | null
  sources?: Source[]
  timestamp?: string
}

// 引用来源
export interface Source {
  id: string
  title: string
  content: string
  score: number
  chunkId?: string
}

// 任务 — 对应文档 4.1.3
export interface Task {
  id: string
  userId: string
  sourceSystem: string
  sourceId: string
  title: string
  description?: string
  status: string
  priority: string
  deadline?: string
  externalUrl?: string
}

// 知识库文档 — 对应文档 4.1.4
export interface KnowledgeDocument {
  id: string
  title: string
  category?: string
  tags?: string[]
  source?: string
  chunkCount: number
  status: string
  createdAt: string
}

// 用户 — 对应文档 4.1.1
export interface User {
  id: string
  username: string
  displayName: string
  email?: string
  department?: string
  role: string
  status: string
}

// 审计日志 — 对应文档 4.1.6
export interface AuditLogEntry {
  id: string
  traceId?: string
  userId: string
  intent: string
  model?: string
  inputTokens: number
  outputTokens: number
  latencyMs: number
  status: string
  createdAt: string
}
