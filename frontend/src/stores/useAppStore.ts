// 全局认证状态仓库：维护登录用户、token 和会话恢复动作。
import { create } from 'zustand';
import { authService, type UserPermission } from '../services/auth';

/** 全局认证状态接口定义 */
interface AppState {
  /** 当前访问令牌（从 localStorage 初始化） */
  token: string | null;
  /** 当前登录用户信息 */
  user: UserPermission | null;
  /** 是否已认证（token 有效且用户信息已加载） */
  isAuthenticated: boolean;
  /** 账号密码登录 */
  login: (username: string, password: string) => Promise<void>;
  /** IAM 统一认证登录（通过授权码） */
  iamLogin: (code: string) => Promise<void>;
  /** 登出并清除认证状态 */
  logout: () => void;
  /** 应用启动时恢复会话：通过 /me 接口重新拉取用户信息 */
  restoreSession: () => Promise<void>;
}

/** Zustand 全局认证状态仓库：维护登录用户、token 和会话恢复动作 */
export const useAppStore = create<AppState>((set) => ({
  token: authService.getToken(),
  user: null,
  isAuthenticated: false,

  login: async (username, password) => {
    const loginData = await authService.login(username, password);
    set({
      token: loginData.token,
      user: loginData.user,
      isAuthenticated: true,
    });
  },

  iamLogin: async (code) => {
    const loginData = await authService.iamLogin(code);
    set({
      token: loginData.token,
      user: loginData.user,
      isAuthenticated: true,
    });
  },

  logout: () => {
    authService.logout();
    set({
      token: null,
      user: null,
      isAuthenticated: false,
    });
  },

  restoreSession: async () => {
    if (!authService.isTokenValid()) {
      authService.logout();
      set({
        token: null,
        user: null,
        isAuthenticated: false,
      });
      return;
    }

    try {
      // 应用启动后通过 /me 恢复用户信息，保证页面展示的是服务端真实身份。
      const user = await authService.getMe();
      set({
        token: authService.getToken(),
        user,
        isAuthenticated: true,
      });
    } catch {
      authService.logout();
      set({
        token: null,
        user: null,
        isAuthenticated: false,
      });
    }
  },
}));
