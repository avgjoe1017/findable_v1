import { apiClient } from './client'
import type {
  Site,
  SiteWithRuns,
  PaginatedResponse,
  CreateSiteRequest
} from '@/types'

export interface ListSitesParams {
  page?: number
  per_page?: number  // Backend uses per_page, not page_size
  search?: string
  sort_by?: 'name' | 'created_at' | 'latest_score'
  sort_order?: 'asc' | 'desc'
}

export const sitesApi = {
  /**
   * List all sites for the current user
   * Backend: GET /v1/sites
   */
  async list(params?: ListSitesParams): Promise<PaginatedResponse<Site>> {
    return apiClient.getPaginated<Site>('/sites', params as Record<string, string | number | boolean | undefined>)
  },

  /**
   * Get a single site by ID
   * Backend: GET /v1/sites/{site_id}
   */
  async get(siteId: string): Promise<SiteWithRuns> {
    return apiClient.get<SiteWithRuns>(`/sites/${siteId}`)
  },

  /**
   * Create a new site
   * Backend: POST /v1/sites
   */
  async create(data: CreateSiteRequest): Promise<Site> {
    return apiClient.post<Site>('/sites', data)
  },

  /**
   * Update a site
   * Backend: PATCH /v1/sites/{site_id}
   */
  async update(siteId: string, data: Partial<CreateSiteRequest>): Promise<Site> {
    return apiClient.patch<Site>(`/sites/${siteId}`, data)
  },

  /**
   * Delete a site
   * Backend: DELETE /v1/sites/{site_id}
   */
  async delete(siteId: string): Promise<void> {
    return apiClient.delete<void>(`/sites/${siteId}`)
  },

  /**
   * Enable monitoring for a site
   * Backend: POST /v1/sites/{site_id}/monitoring
   */
  async enableMonitoring(siteId: string): Promise<Site> {
    return apiClient.post<Site>(`/sites/${siteId}/monitoring`)
  },

  /**
   * Disable monitoring for a site
   * Backend: DELETE /v1/sites/{site_id}/monitoring
   */
  async disableMonitoring(siteId: string): Promise<Site> {
    return apiClient.delete<Site>(`/sites/${siteId}/monitoring`)
  },

  /**
   * Get monitoring status for a site
   * Backend: GET /v1/sites/{site_id}/monitoring
   */
  async getMonitoringStatus(siteId: string): Promise<{ enabled: boolean; interval_hours: number }> {
    return apiClient.get(`/sites/${siteId}/monitoring`)
  },

  /**
   * Update competitors for a site
   * Backend: PUT /v1/sites/{site_id}/competitors
   */
  async updateCompetitors(siteId: string, competitorUrls: string[]): Promise<Site> {
    return apiClient.put<Site>(`/sites/${siteId}/competitors`, { urls: competitorUrls })
  },

  /**
   * Add a competitor to a site (convenience method)
   */
  async addCompetitor(siteId: string, competitorUrl: string): Promise<Site> {
    return sitesApi.updateCompetitors(siteId, [competitorUrl])
  },

  /**
   * Remove a competitor from a site (convenience method)
   */
  async removeCompetitor(siteId: string, competitorId: string): Promise<Site> {
    // Delegate to backend — it handles the removal logic
    return apiClient.delete<Site>(`/sites/${siteId}/competitors/${competitorId}`)
  },

  /**
   * Generate question set for a site
   * Backend: POST /v1/questions/generate
   */
  async generateQuestions(siteId: string): Promise<{ questions: string[] }> {
    return apiClient.post<{ questions: string[] }>('/questions/generate', { site_id: siteId })
  },

  /**
   * Invalidate crawl cache for a site
   * Backend: POST /v1/sites/{site_id}/cache/invalidate
   */
  async invalidateCache(siteId: string): Promise<void> {
    return apiClient.post<void>(`/sites/${siteId}/cache/invalidate`)
  },
}
