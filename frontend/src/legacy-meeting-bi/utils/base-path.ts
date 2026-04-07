export const baseUrl = import.meta.env.BASE_URL ?? '/'

export const normalizedBasePath = baseUrl === '/'
  ? ''
  : baseUrl.replace(/\/$/, '')

const configuredApiBase =
  import.meta.env.VITE_MEETING_BI_API_URL?.trim() ||
  import.meta.env.VITE_BUSINESS_API_URL?.trim() ||
  import.meta.env.VITE_API_BASE_URL?.trim()

// 开发模式下使用空字符串，让请求走 Vite 代理；生产模式下才使用配置的绝对地址。
export const apiBasePath = import.meta.env.DEV
  ? ''
  : (configuredApiBase || (normalizedBasePath ? `${normalizedBasePath}/api` : '/api'))
