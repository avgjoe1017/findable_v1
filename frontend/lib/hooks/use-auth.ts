'use client'

import { useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi } from '@/lib/api'
import { useAuthStore, selectIsAuthenticated, selectIsHydrated, selectToken } from '@/lib/stores'
import type { LoginRequest, RegisterRequest } from '@/types'

export function useAuth() {
  const router = useRouter()
  const queryClient = useQueryClient()

  const isAuthenticated = useAuthStore(selectIsAuthenticated)
  const isHydrated = useAuthStore(selectIsHydrated)
  const token = useAuthStore(selectToken)
  const setAuth = useAuthStore((s) => s.setAuth)
  const setUser = useAuthStore((s) => s.setUser)
  const clearAuth = useAuthStore((s) => s.clearAuth)

  // Fetch current user if we have a token but need fresh data
  const { data: currentUser, isLoading: isLoadingUser } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => authApi.me(),
    enabled: isHydrated && !!token,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false,
  })

  // Update store when user data is fetched
  useEffect(() => {
    if (currentUser) {
      setUser(currentUser)
    }
  }, [currentUser, setUser])

  // Login mutation
  const loginMutation = useMutation({
    mutationFn: (credentials: LoginRequest) => authApi.login(credentials),
    onSuccess: (data) => {
      setAuth(data.user, data.access_token)
      queryClient.invalidateQueries({ queryKey: ['auth'] })
      router.push('/dashboard')
    },
  })

  // Register mutation
  const registerMutation = useMutation({
    mutationFn: (data: RegisterRequest) => authApi.register(data),
    onSuccess: (data) => {
      setAuth(data.user, data.access_token)
      queryClient.invalidateQueries({ queryKey: ['auth'] })
      router.push('/dashboard')
    },
  })

  // Logout mutation
  const logoutMutation = useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => {
      clearAuth()
      queryClient.clear()
      router.push('/login')
    },
    onError: () => {
      // Clear auth even if logout fails (e.g., network error)
      clearAuth()
      queryClient.clear()
      router.push('/login')
    },
  })

  const login = useCallback(
    (credentials: LoginRequest) => loginMutation.mutateAsync(credentials),
    [loginMutation]
  )

  const register = useCallback(
    (data: RegisterRequest) => registerMutation.mutateAsync(data),
    [registerMutation]
  )

  const logout = useCallback(() => logoutMutation.mutate(), [logoutMutation])

  return {
    user: currentUser ?? useAuthStore.getState().user,
    isAuthenticated,
    isHydrated,
    isLoading: !isHydrated || isLoadingUser,
    login,
    register,
    logout,
    loginError: loginMutation.error,
    registerError: registerMutation.error,
    isLoggingIn: loginMutation.isPending,
    isRegistering: registerMutation.isPending,
    isLoggingOut: logoutMutation.isPending,
  }
}
