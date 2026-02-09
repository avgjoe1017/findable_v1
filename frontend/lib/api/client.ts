import type { ApiError } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Backend response format:
 * - Success: { data: T, meta?: { total, page, per_page, ... } }
 * - Error: { error: { code, message, field?, details? } }
 */
interface BackendResponse<T> {
  data: T
  meta?: {
    total?: number
    page?: number
    per_page?: number
    total_pages?: number
    has_next?: boolean
    has_prev?: boolean
    [key: string]: unknown
  }
}

interface BackendPaginatedResponse<T> {
  data: T[]
  meta: {
    total: number
    page: number
    per_page: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
  }
}

export class ApiClient {
  private baseUrl: string
  private getToken: () => string | null

  constructor(baseUrl: string = API_URL, getToken?: () => string | null) {
    this.baseUrl = baseUrl
    this.getToken = getToken || (() => {
      if (typeof window === 'undefined') return null
      return localStorage.getItem('auth_token')
    })
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken()

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options.headers as Record<string, string>,
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const url = `${this.baseUrl}/v1${endpoint}`

    const response = await fetch(url, {
      ...options,
      headers,
    })

    // Handle no content responses
    if (response.status === 204) {
      return undefined as T
    }

    const json = await response.json()

    if (!response.ok) {
      const error = json as ApiError
      throw new ApiClientError(
        error.error?.message || 'An error occurred',
        response.status,
        error.error?.code || 'UNKNOWN_ERROR',
        error.error?.details
      )
    }

    // Backend returns { data: T, meta?: {...} }
    // Extract just the data portion
    const backendResponse = json as BackendResponse<T>
    return backendResponse.data
  }

  /**
   * GET request - returns data directly
   */
  async get<T, P extends Record<string, string | number | boolean | undefined> = Record<string, string | number | boolean | undefined>>(
    endpoint: string,
    params?: P
  ): Promise<T> {
    const searchParams = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, String(value))
        }
      })
    }
    const queryString = searchParams.toString()
    const url = queryString ? `${endpoint}?${queryString}` : endpoint

    return this.request<T>(url, { method: 'GET' })
  }

  /**
   * GET paginated request - transforms backend pagination to frontend format
   */
  async getPaginated<T>(
    endpoint: string,
    params?: Record<string, string | number | boolean | undefined>
  ): Promise<{ items: T[]; total: number; page: number; page_size: number; total_pages: number }> {
    const searchParams = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.append(key, String(value))
        }
      })
    }
    const queryString = searchParams.toString()
    const url = queryString ? `${endpoint}?${queryString}` : endpoint

    const token = this.getToken()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${this.baseUrl}/v1${url}`, {
      method: 'GET',
      headers,
    })

    const json = await response.json()

    if (!response.ok) {
      const error = json as ApiError
      throw new ApiClientError(
        error.error?.message || 'An error occurred',
        response.status,
        error.error?.code || 'UNKNOWN_ERROR',
        error.error?.details
      )
    }

    // Transform backend pagination format to frontend format
    const backendResponse = json as BackendPaginatedResponse<T>
    return {
      items: backendResponse.data,
      total: backendResponse.meta.total,
      page: backendResponse.meta.page,
      page_size: backendResponse.meta.per_page,
      total_pages: backendResponse.meta.total_pages,
    }
  }

  async post<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(body ?? {}),
    })
  }

  async put<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async patch<T>(endpoint: string, body?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    })
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }

  /**
   * Create SSE connection for real-time updates
   * Note: Backend needs to support ?token= query param since EventSource
   * doesn't support custom headers
   */
  createEventSource(endpoint: string): EventSource {
    const token = this.getToken()
    const url = new URL(`${this.baseUrl}/v1${endpoint}`)

    // Pass token as query param for SSE (EventSource doesn't support headers)
    if (token) {
      url.searchParams.set('token', token)
    }

    return new EventSource(url.toString())
  }
}

export class ApiClientError extends Error {
  status: number
  code: string
  details?: Record<string, unknown>

  constructor(
    message: string,
    status: number,
    code: string,
    details?: Record<string, unknown>
  ) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
    this.details = details
  }

  get isUnauthorized(): boolean {
    return this.status === 401
  }

  get isForbidden(): boolean {
    return this.status === 403
  }

  get isNotFound(): boolean {
    return this.status === 404
  }

  get isValidationError(): boolean {
    return this.status === 422
  }

  get isRateLimited(): boolean {
    return this.status === 429
  }
}

// Default client instance
export const apiClient = new ApiClient()
