// 全局认证状态仓库：维护登录用户、token 和会话恢复动作。
import { create } from 'zustand';
import { authService, type UserPermission } from '../services/auth';

interface AppState {
  token: string | null;
  user: UserPermission | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  iamLogin: (code: string) => Promise<void>;
  logout: () => void;
  restoreSession: () => Promise<void>;
}

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
