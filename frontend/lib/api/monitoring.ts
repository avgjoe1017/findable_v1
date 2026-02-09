import { apiClient } from './client'
import type { Snapshot, Alert, PaginatedResponse } from '@/types'

export interface ListSnapshotsParams {
  page?: number
  per_page?: number
  start_date?: string
  end_date?: string
}

export interface ListAlertsParams {
  page?: number
  per_page?: number
  acknowledged?: boolean
  site_id?: string
}

export interface SnapshotTrend {
  date: string
  score: number
  grade: string
}

export const monitoringApi = {
  /**
   * List snapshots for a site
   * Backend: GET /v1/sites/{site_id}/snapshots
   */
  async listSnapshots(siteId: string, params?: ListSnapshotsParams): Promise<PaginatedResponse<Snapshot>> {
    return apiClient.getPaginated<Snapshot>(`/sites/${siteId}/snapshots`, params as Record<string, string | number | boolean | undefined>)
  },

  /**
   * Get a single snapshot
   * Backend: GET /v1/sites/{site_id}/snapshots/{snapshot_id}
   */
  async getSnapshot(siteId: string, snapshotId: string): Promise<Snapshot> {
    return apiClient.get<Snapshot>(`/sites/${siteId}/snapshots/${snapshotId}`)
  },

  /**
   * Get score trend data for charting
   * Backend: GET /v1/sites/{site_id}/snapshots/trend
   */
  async getTrend(siteId: string, days?: number): Promise<SnapshotTrend[]> {
    return apiClient.get<SnapshotTrend[]>(`/sites/${siteId}/snapshots/trend`, { days })
  },

  /**
   * Trigger a manual snapshot
   * Backend: POST /v1/sites/{site_id}/monitoring/snapshot
   */
  async triggerSnapshot(siteId: string): Promise<Snapshot> {
    return apiClient.post<Snapshot>(`/sites/${siteId}/monitoring/snapshot`)
  },

  /**
   * List alerts (optionally filtered by site)
   * Backend: GET /v1/alerts
   */
  async listAlerts(params?: ListAlertsParams): Promise<PaginatedResponse<Alert>> {
    return apiClient.getPaginated<Alert>('/alerts', params as Record<string, string | number | boolean | undefined>)
  },

  /**
   * List alerts for a specific site
   */
  async listAlertsForSite(siteId: string, params?: Omit<ListAlertsParams, 'site_id'>): Promise<PaginatedResponse<Alert>> {
    return apiClient.getPaginated<Alert>('/alerts', { ...params, site_id: siteId } as Record<string, string | number | boolean | undefined>)
  },

  /**
   * Get a single alert
   * Backend: GET /v1/alerts/{alert_id}
   */
  async getAlert(alertId: string): Promise<Alert> {
    return apiClient.get<Alert>(`/alerts/${alertId}`)
  },

  /**
   * Acknowledge alerts
   * Backend: POST /v1/alerts/acknowledge
   */
  async acknowledgeAlerts(alertIds: string[]): Promise<void> {
    return apiClient.post<void>('/alerts/acknowledge', { alert_ids: alertIds })
  },

  /**
   * Acknowledge a single alert (convenience method)
   */
  async acknowledgeAlert(alertId: string): Promise<void> {
    return monitoringApi.acknowledgeAlerts([alertId])
  },

  /**
   * Dismiss alerts
   * Backend: POST /v1/alerts/dismiss
   */
  async dismissAlerts(alertIds: string[]): Promise<void> {
    return apiClient.post<void>('/alerts/dismiss', { alert_ids: alertIds })
  },

  /**
   * Get alert statistics
   * Backend: GET /v1/alerts/stats
   */
  async getAlertStats(): Promise<{
    total: number
    unacknowledged: number
    by_type: Record<string, number>
  }> {
    return apiClient.get('/alerts/stats')
  },

  /**
   * Get alert configuration for a site
   * Backend: GET /v1/sites/{site_id}/alerts/config
   */
  async getAlertConfig(siteId: string): Promise<AlertSettings> {
    return apiClient.get<AlertSettings>(`/sites/${siteId}/alerts/config`)
  },

  /**
   * Create or update alert configuration
   * Backend: POST /v1/sites/{site_id}/alerts/config (create)
   * Backend: PATCH /v1/sites/{site_id}/alerts/config (update)
   */
  async configureAlerts(siteId: string, settings: Partial<AlertSettings>): Promise<AlertSettings> {
    return apiClient.patch<AlertSettings>(`/sites/${siteId}/alerts/config`, settings)
  },
}

export interface AlertSettings {
  score_drop_threshold: number
  competitor_overtake_enabled: boolean
  observation_divergence_enabled: boolean
  email_notifications: boolean
  webhook_url?: string
}
