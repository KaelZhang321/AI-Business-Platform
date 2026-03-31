export const baseUrl = import.meta.env.BASE_URL ?? '/'

export const normalizedBasePath = baseUrl === '/'
  ? ''
  : baseUrl.replace(/\/$/, '')

const configuredApiBase =
  import.meta.env.VITE_MEETING_BI_API_URL?.trim() ||
  import.meta.env.VITE_BUSINESS_API_URL?.trim() ||
  import.meta.env.VITE_API_BASE_URL?.trim()

export const apiBasePath = configuredApiBase || (
  normalizedBasePath
    ? `${normalizedBasePath}/api`
    : '/api'
)
