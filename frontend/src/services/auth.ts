import { jwtDecode } from 'jwt-decode'
import { businessClient } from './api'

const TOKEN_KEY = 'ai_platform_token'
const REFRESH_TOKEN_KEY = 'ai_platform_refresh_token'

export interface JwtPayload {
  sub: string
  exp: number
  iat: number
}

export interface UserPermission {
  id: string
  username: string
  displayName: string
  role: string
  abilities: string[]
}

export interface LoginResponse {
  token: string
  refreshToken: string
  expiresIn: number
  user: UserPermission
}

export const authService = {
  async login(username: string, password: string): Promise<LoginResponse> {
    const res = await businessClient.post<{ code: number; message: string; data: LoginResponse }>(
      '/api/v1/auth/login',
      { username, password },
    )
    const loginData = res.data.data
    localStorage.setItem(TOKEN_KEY, loginData.token)
    if (loginData.refreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, loginData.refreshToken)
    }
    return loginData
  },

  async getMe(): Promise<UserPermission> {
    const res = await businessClient.get<{ code: number; message: string; data: UserPermission }>(
      '/api/v1/auth/me',
    )
    return res.data.data
  },

  logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY)
  },

  setToken(token: string) {
    localStorage.setItem(TOKEN_KEY, token)
  },

  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY)
  },

  isTokenValid(): boolean {
    const token = this.getToken()
    if (!token) return false
    try {
      const decoded = jwtDecode<JwtPayload>(token)
      return decoded.exp * 1000 > Date.now()
    } catch {
      return false
    }
  },

  /** SSO/Keycloak 登录 — 重定向到 Keycloak 授权端点 */
  loginWithSSO() {
    const keycloakUrl = import.meta.env.VITE_KEYCLOAK_URL
    if (!keycloakUrl) return
    const realm = import.meta.env.VITE_KEYCLOAK_REALM || 'ai-platform'
    const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'ai-platform-frontend'
    const url = new URL(`${keycloakUrl}/realms/${realm}/protocol/openid-connect/auth`)
    const callbackUrl = new URL(`${import.meta.env.BASE_URL}sso/callback`, window.location.origin)
    url.searchParams.set('client_id', clientId)
    url.searchParams.set('response_type', 'code')
    url.searchParams.set('scope', 'openid')
    url.searchParams.set('redirect_uri', callbackUrl.toString())
    window.location.href = url.toString()
  },

  /** SSO 是否已配置启用 */
  isSSOEnabled(): boolean {
    return !!import.meta.env.VITE_KEYCLOAK_URL
  },
}
