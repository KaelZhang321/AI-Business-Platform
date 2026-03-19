import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

const businessClient = axios.create({
  baseURL: import.meta.env.VITE_BUSINESS_API_URL || 'http://localhost:8080',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// AI 网关 API
export const chatAPI = {
  send: (message: string, conversationId?: string) =>
    apiClient.post('/api/v1/chat', { message, conversation_id: conversationId, user_id: 'default' }),
}

export const knowledgeAPI = {
  search: (query: string, topK = 5) =>
    apiClient.post('/api/v1/knowledge/search', { query, top_k: topK }),
}

export const queryAPI = {
  text2sql: (question: string) =>
    apiClient.post('/api/v1/query/text2sql', { question }),
}

// 业务编排层 API
export const taskAPI = {
  aggregate: (params?: { userId?: string; status?: string; page?: number; size?: number }) =>
    businessClient.get('/api/v1/tasks/aggregate', { params }),
}

export const documentAPI = {
  list: (page = 1, size = 20) =>
    businessClient.get('/api/v1/knowledge/documents', { params: { page, size } }),
  create: (data: Record<string, unknown>) =>
    businessClient.post('/api/v1/knowledge/documents', data),
}

export const auditAPI = {
  logs: (params?: { userId?: string; action?: string; page?: number; size?: number }) =>
    businessClient.get('/api/v1/audit/logs', { params }),
}
