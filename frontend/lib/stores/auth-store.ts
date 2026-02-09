import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { User } from '@/types'

interface AuthState {
  user: User | null
  token: string | null
  isHydrated: boolean

  // Actions
  setAuth: (user: User, token: string) => void
  setUser: (user: User) => void
  clearAuth: () => void
  setHydrated: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isHydrated: false,

      setAuth: (user, token) => {
        // Also set token in localStorage for API client
        if (typeof window !== 'undefined') {
          localStorage.setItem('auth_token', token)
        }
        set({ user, token })
      },

      setUser: (user) => set({ user }),

      clearAuth: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('auth_token')
        }
        set({ user: null, token: null })
      },

      setHydrated: () => set({ isHydrated: true }),
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        token: state.token,
      }),
      onRehydrateStorage: () => (state) => {
        // Sync token to localStorage for API client on rehydrate
        if (state?.token && typeof window !== 'undefined') {
          localStorage.setItem('auth_token', state.token)
        }
        state?.setHydrated()
      },
    }
  )
)

// Selectors for optimal re-renders
export const selectUser = (state: AuthState) => state.user
export const selectToken = (state: AuthState) => state.token
export const selectIsAuthenticated = (state: AuthState) => !!state.token && !!state.user
export const selectIsHydrated = (state: AuthState) => state.isHydrated
