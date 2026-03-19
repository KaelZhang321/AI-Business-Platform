import { create } from 'zustand'

interface AppState {
  currentUser: { id: string; name: string } | null
  sidebarCollapsed: boolean
  chatVisible: boolean
  setCurrentUser: (user: { id: string; name: string } | null) => void
  toggleSidebar: () => void
  setChatVisible: (visible: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  currentUser: null,
  sidebarCollapsed: false,
  chatVisible: true,
  setCurrentUser: (user) => set({ currentUser: user }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setChatVisible: (visible) => set({ chatVisible: visible }),
}))
