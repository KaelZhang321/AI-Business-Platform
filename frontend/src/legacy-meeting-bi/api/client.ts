// 接口服务层：统一创建带鉴权和自动刷新能力的 Axios 客户端。
import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios';

/** localStorage 中存储用户访问令牌的键名 */
const TOKEN_KEY = 'ai_platform_token';
/** localStorage 中存储刷新令牌的键名 */
const REFRESH_TOKEN_KEY = 'ai_platform_refresh_token';

/** 从本地存储读取访问令牌 */
function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

/** 从本地存储读取刷新令牌 */
function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/** 清除本地存储中的所有认证信息（token + refreshToken） */
function clearAuthStorage() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/** 登出通知：清除本地认证并广播全局事件，让应用层统一处理跳转 */
function notifyAuthLogout() {
  clearAuthStorage();
  // 通过全局事件把“鉴权已失效”广播给应用层，避免服务层直接依赖 UI。
  window.dispatchEvent(new CustomEvent('auth:logout'));
}

/**
 * 请求拦截器：在每个 HTTP 请求发出前自动注入认证头。
 * @param config - Axios 请求配置
 * @returns 附加了 CToken / DeviceId 的请求配置
 */
function attachToken(config: InternalAxiosRequestConfig) {
  const token = getToken();
  if (token) {
    // 统一在请求发出前注入 Bearer token。
    config.headers.CToken = `${token}`;
    config.headers.DeviceId = `pc`;
    // config.headers['X-User-Id'] = `2`;
  }
  return config;
}

/**
 * 使用 refreshToken 向后端换取新的 accessToken。
 * @param baseURL - 接口基请求地址
 * @returns 新的 accessToken 字符串
 */
async function refreshAccessToken(baseURL: string) {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    throw new Error('no refresh token');
  }

  const response = await axios.post<{ token: string; expiresIn: number }>(
    `${baseURL}/api/v1/auth/refresh`,
    null,
    {
      headers: {
        CToken: `${refreshToken}`,
        DeviceId: `pc`,
        // 'X-User-Id': `2`,
      },
    },
  );

  localStorage.setItem(TOKEN_KEY, response.data.token);
  return response.data.token;
}

/** 当前正在进行的 token 刷新 Promise，用于防止多个 401 同时触发重复刷新 */
let refreshPromise: Promise<string> | null = null;

/**
 * 创建带自动鉴权和 401 自动刷新能力的 Axios 客户端。
 * @param baseURL - 接口基地址
 * @param timeout - 请求超时时间（毫秒），默认 15 秒
 * @returns 配置好拦截器的 Axios 实例
 */
export function createClient(baseURL: string, timeout = 15_000): AxiosInstance {
  const client = axios.create({
    baseURL,
    timeout,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  client.interceptors.request.use(attachToken);
  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as
        | (InternalAxiosRequestConfig & { _retried?: boolean })
        | undefined;

      if (!originalRequest || error.response?.status !== 401) {
        return Promise.reject(error);
      }

      if (originalRequest._retried || originalRequest.url?.includes('/api/v1/auth/refreshAuthToken')) {
        notifyAuthLogout();
        return Promise.reject(error);
      }

      originalRequest._retried = true;

      try {
        if (!refreshPromise) {
          // 共享刷新 Promise，避免多个 401 同时触发多次 refresh 请求。
          refreshPromise = refreshAccessToken(baseURL).finally(() => {
            refreshPromise = null;
          });
        }

        const newToken = await refreshPromise;
        originalRequest.headers.CToken = `${newToken}`;
        return client(originalRequest);
      } catch {
        notifyAuthLogout();
        return Promise.reject(error);
      }
    },
  );

  return client;
}

/**
 * 获取接口基地址：优先使用环境变量，否则回退到 Vite 的 BASE_URL。
 * @param envUrl - 可选的环境变量值
 * @returns 去除尾部斜杠的基址字符串
 */
const getBaseUrl = (envUrl?: string) => {
  if (envUrl?.trim()) return envUrl.trim();
  const base = import.meta.env.BASE_URL || '';
  return base.endsWith('/') ? base.slice(0, -1) : base;
};

/** AI 网关客户端（长超时 300s，适用于 AI 推理等耗时接口） */
export const apiClient = createClient(getBaseUrl(import.meta.env.VITE_API_BASE_URL), 300_000);
/** 业务编排客户端（标准超时 15s，适用于常规 CRUD 接口） */
export const businessClient = createClient(getBaseUrl(import.meta.env.VITE_BUSINESS_API_URL), 15_000);


export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

