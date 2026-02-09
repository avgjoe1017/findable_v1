import { apiClient } from './client'
import type { Plan, Usage, PlanTier } from '@/types'

export const billingApi = {
  /**
   * Get all available plans
   * Backend: GET /v1/billing/plans
   */
  async getPlans(): Promise<Plan[]> {
    return apiClient.get<Plan[]>('/billing/plans')
  },

  /**
   * Get specific plan limits
   * Backend: GET /v1/billing/plans/{plan}
   */
  async getPlanLimits(plan: PlanTier): Promise<Plan> {
    return apiClient.get<Plan>(`/billing/plans/${plan}`)
  },

  /**
   * Get current subscription details
   * Backend: GET /v1/billing/subscription
   */
  async getSubscription(): Promise<{
    plan: PlanTier
    status: string
    current_period_end: string
    cancel_at_period_end: boolean
  }> {
    return apiClient.get('/billing/subscription')
  },

  /**
   * Get current usage
   * Backend: GET /v1/billing/usage
   */
  async getUsage(): Promise<Usage> {
    return apiClient.get<Usage>('/billing/usage')
  },

  /**
   * Check site limit
   * Backend: GET /v1/billing/limits/sites
   */
  async checkSiteLimit(): Promise<{ allowed: boolean; current: number; limit: number }> {
    return apiClient.get('/billing/limits/sites')
  },

  /**
   * Check run limit
   * Backend: GET /v1/billing/limits/runs
   */
  async checkRunLimit(): Promise<{ allowed: boolean; current: number; limit: number }> {
    return apiClient.get('/billing/limits/runs')
  },

  /**
   * Check feature access
   * Backend: GET /v1/billing/features/{feature}
   */
  async checkFeature(feature: string): Promise<{ allowed: boolean }> {
    return apiClient.get(`/billing/features/${feature}`)
  },

  /**
   * Create a checkout session for plan upgrade
   * Backend: POST /v1/billing/checkout
   */
  async createCheckout(tier: PlanTier, interval: 'monthly' | 'yearly'): Promise<{ url: string }> {
    return apiClient.post<{ url: string }>('/billing/checkout', {
      plan: tier,
      interval,
      success_url: `${window.location.origin}/billing?success=true`,
      cancel_url: `${window.location.origin}/billing?canceled=true`,
    })
  },

  /**
   * Create a portal session for subscription management
   * Backend: POST /v1/billing/portal
   */
  async createPortal(): Promise<{ url: string }> {
    return apiClient.post<{ url: string }>('/billing/portal', {
      return_url: `${window.location.origin}/billing`,
    })
  },

  /**
   * Get billing/invoice history
   * Backend: GET /v1/billing/history
   */
  async getHistory(): Promise<Invoice[]> {
    const response = await apiClient.getPaginated<Invoice>('/billing/history')
    return response.items
  },
}

export interface Invoice {
  id: string
  amount: number
  currency: string
  status: 'paid' | 'pending' | 'failed'
  date: string
  pdf_url?: string
  description?: string
}
