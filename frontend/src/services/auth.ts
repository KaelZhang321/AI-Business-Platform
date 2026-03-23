import { jwtDecode } from 'jwt-decode'
import { businessClient } from './api'

const TOKEN_KEY = 'ai_platform_token'

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
}
