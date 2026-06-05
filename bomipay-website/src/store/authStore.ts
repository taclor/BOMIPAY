import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types/api'

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  setAuth: (token: string, user: User | null) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setAuth: (token, user) => {
        set({ token, user: user ?? null, isAuthenticated: true })
        if (typeof window !== 'undefined') {
          localStorage.setItem('token', token)
        }
      },
      clearAuth: () => {
        set({ token: null, user: null, isAuthenticated: false })
        if (typeof window !== 'undefined') {
          localStorage.removeItem('token')
        }
      },
    }),
    {
      name: 'bomipay-auth',
      partialize: (state) => ({ token: state.token, user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)
