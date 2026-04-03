// 接口服务层：统一创建带鉴权和自动刷新能力的 Axios 客户端。
import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios';

const TOKEN_KEY = 'ai_platform_token';
const REFRESH_TOKEN_KEY = 'ai_platform_refresh_token';

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

function clearAuthStorage() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

function notifyAuthLogout() {
  clearAuthStorage();
  // 通过全局事件把“鉴权已失效”广播给应用层，避免服务层直接依赖 UI。
  window.dispatchEvent(new CustomEvent('auth:logout'));
}

function attachToken(config: InternalAxiosRequestConfig) {
  const token = getToken();
  if (token) {
    // 统一在请求发出前注入 Bearer token。
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}

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
        Authorization: `Bearer ${refreshToken}`,
      },
    },
  );

  localStorage.setItem(TOKEN_KEY, response.data.token);
  return response.data.token;
}

let refreshPromise: Promise<string> | null = null;

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

      if (originalRequest._retried || originalRequest.url?.includes('/api/v1/auth/refresh')) {
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
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return client(originalRequest);
      } catch {
        notifyAuthLogout();
        return Promise.reject(error);
      }
    },
  );

  return client;
}

const getBaseUrl = (envUrl?: string) => {
  if (envUrl?.trim()) return envUrl.trim();
  const base = import.meta.env.BASE_URL || '';
  return base.endsWith('/') ? base.slice(0, -1) : base;
};

export const apiClient = createClient(getBaseUrl(import.meta.env.VITE_API_BASE_URL), 30_000);
export const businessClient = createClient(getBaseUrl(import.meta.env.VITE_BUSINESS_API_URL), 15_000);
