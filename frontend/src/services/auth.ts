// 认证服务层：封装登录、登出、用户信息获取和 token 有效性判断。
import { jwtDecode } from 'jwt-decode';
import { businessClient } from './api';

/** localStorage 中存储用户访问令牌的键名 */
const TOKEN_KEY = 'ai_platform_token';
/** localStorage 中存储刷新令牌的键名 */
const REFRESH_TOKEN_KEY = 'ai_platform_refresh_token';

/** JWT 载荷结构 —— 从 token 中解码出的标准字段 */
export interface JwtPayload {
  /** 用户标识（subject） */
  sub: string;
  /** 过期时间（Unix 秒） */
  exp: number;
  /** 签发时间（Unix 秒） */
  iat: number;
}

/** 用户权限信息 —— 后端 /auth/info 接口返回的用户数据 */
export interface UserPermission {
  /** 用户 ID */
  id: string;
  /** 登录账号 */
  username: string;
  /** 显示名称 */
  displayName: string;
  /** 角色名称 */
  role: string;
  /** 功能权限列表 */
  abilities: string[];
}

/** 登录接口返回数据 */
export interface LoginResponse {
  /** 访问令牌 */
  token: string
  /** 刷新令牌 */
  refreshToken: string
  /** 有效期（秒） */
  expiresIn: number
  /** 用户权限信息 */
  user: UserPermission
}

/** 后端统一包装格式：用于 /auth/info 等接口 */
interface WrappedUserPermission {
  code: number;
  message: string;
  data: UserPermission;
}

/** 认证服务对象：封装登录、登出、用户信息获取和 token 有效性判断 */
export const authService = {
  /** 账号密码登录 */
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

  /** IAM 统一认证登录：使用授权码换取 token */
  async iamLogin(code: string): Promise<LoginResponse> {
    const response = await businessClient.get<LoginResponse>('/api/v1/auth/getAuthTokenByCode', {
      params: { code },
    });
    const loginData = response.data;
    localStorage.setItem(TOKEN_KEY, loginData.token);
    if (loginData.refreshToken) {
      localStorage.setItem(REFRESH_TOKEN_KEY, loginData.refreshToken);
    }
    console.log(loginData)

    return loginData;
  },

  /** 获取当前用户信息（兼容裸 UserPermission 和 code/message/data 包装格式） */
  async getMe(): Promise<UserPermission> {
    const response = await businessClient.get<UserPermission | WrappedUserPermission>(
      '/api/v1/auth/info',
    );

    if ('data' in response.data) {
      return response.data.data;
    }

    return response.data;
  },

  /** 登出：清除本地 token 存储 */
  logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },

  /** 读取当前保存的访问令牌 */
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  /** 读取当前保存的刷新令牌 */
  getRefreshToken() {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  /** 手动设置访问令牌（供外部回调使用） */
  setToken(token: string) {
    localStorage.setItem(TOKEN_KEY, token);
  },

  /** 判断当前 token 是否仍在有效期内（前端判断，真实权限以后端为准） */
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
