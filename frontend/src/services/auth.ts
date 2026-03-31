// 认证服务层：封装登录、登出、用户信息获取和 token 有效性判断。
import { jwtDecode } from 'jwt-decode';
import { businessClient } from './api';

const TOKEN_KEY = 'ai_platform_token';
const REFRESH_TOKEN_KEY = 'ai_platform_refresh_token';

export interface JwtPayload {
  sub: string;
  exp: number;
  iat: number;
}

export interface UserPermission {
  id: string;
  username: string;
  displayName: string;
  role: string;
  abilities: string[];
}

export interface LoginResponse {
  token: string
  refreshToken: string
  expiresIn: number
  user: UserPermission
}
interface WrappedUserPermission {
  code: number;
  message: string;
  data: UserPermission;
}

export const authService = {
  async login(username: string, password: string): Promise<LoginResponse> {
    const response = await businessClient.post<LoginResponse>('/api/v1/auth/login', {
      username,
      password,
    });

    const loginData = response.data;
    // 登录成功后立即持久化 token，供页面刷新和接口拦截器复用。
    localStorage.setItem(TOKEN_KEY, loginData.token);
    if (loginData.refreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, loginData.refreshToken);
    }

    return loginData;
  },

  async getMe(): Promise<UserPermission> {
    const response = await businessClient.get<UserPermission | WrappedUserPermission>(
      '/api/v1/auth/me',
    );

    if ('data' in response.data) {
      return response.data.data;
    }

    return response.data;
  },

  logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },

  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  getRefreshToken() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  setToken(token: string) {
    localStorage.setItem(TOKEN_KEY, token);
  },

  isTokenValid() {
    const token = this.getToken();
    if (!token) {
      return false;
    }

    try {
      // 仅做前端过期时间判断，真实权限仍以后端校验为准。
      const decoded = jwtDecode<JwtPayload>(token);
      return decoded.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  },
};
