import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { authService } from './auth'

const TOKEN_KEY = 'ai_platform_token'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

export const businessClient = axios.create({
  baseURL: import.meta.env.VITE_BUSINESS_API_URL || '',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// JWT interceptor — 为所有请求自动附加 Authorization header
function attachToken(config: import('axios').InternalAxiosRequestConfig) {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}

apiClient.interceptors.request.use(attachToken)
businessClient.interceptors.request.use(attachToken)

// 401 响应拦截 — 使用共享 Promise 消除竞态条件
let refreshPromise: Promise<string> | null = null

function redirectToLogin() {
  authService.logout()
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

function doRefresh(): Promise<string> {
  const refreshToken = authService.getRefreshToken()
  if (!refreshToken) {
    return Promise.reject(new Error('no refresh token'))
  }
  return axios
    .post<{ token: string; expiresIn: number }>(
      `${businessClient.defaults.baseURL}/api/v1/auth/refresh`,
      null,
      { headers: { Authorization: `Bearer ${refreshToken}` } },
    )
    .then((res) => {
      const newToken = res.data.token
      authService.setToken(newToken)
      return newToken
    })
}

async function handle401(error: AxiosError) {
  const originalRequest = error.config as InternalAxiosRequestConfig & { _retried?: boolean }
  if (error.response?.status !== 401 || !originalRequest || originalRequest._retried) {
    if (error.response?.status === 401) redirectToLogin()
    return Promise.reject(error)
  }
  if (originalRequest.url?.includes('/api/v1/auth/refresh')) {
    redirectToLogin()
    return Promise.reject(error)
  }

  originalRequest._retried = true

  // 所有并发 401 共享同一个刷新 Promise，避免竞态
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => { refreshPromise = null })
  }

  try {
    const newToken = await refreshPromise
    originalRequest.headers.Authorization = `Bearer ${newToken}`
    return businessClient(originalRequest)
  } catch {
    redirectToLogin()
    return Promise.reject(error)
  }
}

apiClient.interceptors.response.use((r) => r, handle401)
businessClient.interceptors.response.use((r) => r, handle401)

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
  logs: (params?: { userId?: string; intent?: string; status?: string; page?: number; size?: number }) =>
    businessClient.get('/api/v1/audit/logs', { params }),
}
