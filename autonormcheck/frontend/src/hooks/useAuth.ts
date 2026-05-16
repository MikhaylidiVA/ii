import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: { id: string; email: string; role: string } | null
  isAuthenticated: boolean
  login: (token: string, refreshToken: string, user: any) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      login: (token, refreshToken, user) =>
        set({ token, refreshToken, user, isAuthenticated: true }),
      logout: () => set({ token: null, refreshToken: null, user: null, isAuthenticated: false }),
    }),
    { name: 'auth-storage' }
  )
)
