import { apiClient } from './client'
import type { User, AuthResponse, LoginRequest, RegisterRequest } from '@/types'

export const authApi = {
  /**
   * Login with email and password
   * Backend: POST /v1/auth/login
   */
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    // FastAPI-Users expects form data for login
    const formData = new URLSearchParams()
    formData.append('username', credentials.email) // FastAPI-Users uses 'username' field
    formData.append('password', credentials.password)

    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/v1/auth/login`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Login failed')
    }

    const data = await response.json()

    // FastAPI-Users returns { access_token, token_type }
    // We need to fetch the user separately
    const user = await authApi.meWithToken(data.access_token)

    return {
      user,
      access_token: data.access_token,
      token_type: data.token_type,
    }
  },

  /**
   * Register a new user
   * Backend: POST /v1/auth/register
   */
  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/v1/auth/register`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: data.email,
          password: data.password,
          name: data.name,
        }),
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Registration failed')
    }

    // After registration, log the user in
    return authApi.login({ email: data.email, password: data.password })
  },

  /**
   * Logout the current user
   * Backend: POST /v1/auth/logout
   */
  async logout(): Promise<void> {
    try {
      await apiClient.post<void>('/auth/logout')
    } catch {
      // Ignore logout errors - we'll clear local state anyway
    }
  },

  /**
   * Get the current authenticated user
   * Backend: GET /v1/auth/users/me
   * Note: FastAPI-Users returns user directly (no { data: ... } wrapper)
   */
  async me(): Promise<User> {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
    if (!token) {
      throw new Error('No auth token')
    }

    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/v1/auth/users/me`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    )

    if (!response.ok) {
      throw new Error('Failed to fetch user')
    }

    const json = await response.json()
    return json.data || json // Handle both wrapped and unwrapped responses
  },

  /**
   * Get user with a specific token (used during login)
   */
  async meWithToken(token: string): Promise<User> {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/v1/auth/users/me`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    )

    if (!response.ok) {
      throw new Error('Failed to fetch user')
    }

    const json = await response.json()
    return json.data || json // Handle both wrapped and unwrapped responses
  },

  /**
   * Refresh the access token
   * Note: FastAPI-Users doesn't have a refresh endpoint by default
   * This is a placeholder if you add one
   */
  async refresh(): Promise<AuthResponse> {
    throw new Error('Token refresh not implemented')
  },
}
