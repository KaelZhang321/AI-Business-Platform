import { create } from 'zustand'
import { authService, type UserPermission } from '../services/auth'
import { defineAbilityFor, type AppAbility } from '../abilities'

interface AppState {
  // 认证
  token: string | null
  user: UserPermission | null
  ability: AppAbility | null
  isAuthenticated: boolean

  // UI
  sidebarCollapsed: boolean
  chatVisible: boolean

  // Actions
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  restoreSession: () => Promise<void>
  toggleSidebar: () => void
  setChatVisible: (visible: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  token: authService.getToken(),
  user: null,
  ability: null,
  isAuthenticated: false,
  sidebarCollapsed: false,
  chatVisible: true,

  login: async (username, password) => {
    const loginData = await authService.login(username, password)
    const ability = defineAbilityFor(loginData.user.role)
    set({
      token: loginData.token,
      user: loginData.user,
      ability,
      isAuthenticated: true,
    })
  },

  logout: () => {
    authService.logout()
    set({
      token: null,
      user: null,
      ability: null,
      isAuthenticated: false,
    })
  },

  restoreSession: async () => {
    if (!authService.isTokenValid()) {
      authService.logout()
      set({ token: null, user: null, ability: null, isAuthenticated: false })
      return
    }
    try {
      const user = await authService.getMe()
      const ability = defineAbilityFor(user.role)
      set({
        token: authService.getToken(),
        user,
        ability,
        isAuthenticated: true,
      })
    } catch {
      authService.logout()
      set({ token: null, user: null, ability: null, isAuthenticated: false })
    }
  },

  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setChatVisible: (visible) => set({ chatVisible: visible }),
}))
