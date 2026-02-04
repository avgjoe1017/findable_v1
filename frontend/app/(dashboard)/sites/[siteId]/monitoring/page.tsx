'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Bell, BellOff, Loader2, Check, AlertTriangle, TrendingDown } from 'lucide-react'
import { format } from 'date-fns'
import { sitesApi, monitoringApi } from '@/lib/api'
import { toast } from '@/lib/hooks'
import { cn, formatRelativeTime } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { GradeBadge, Skeleton } from '@/components/shared'
import { TrendChart } from '@/components/report'
import type { Alert, AlertSeverity } from '@/types'

interface MonitoringPageProps {
  params: { siteId: string }
}

export default function MonitoringPage({ params }: MonitoringPageProps) {
  const { siteId } = params
  const queryClient = useQueryClient()

  const { data: site, isLoading: isLoadingSite } = useQuery({
    queryKey: ['sites', siteId],
    queryFn: () => sitesApi.get(siteId),
  })

  const { data: snapshotsData, isLoading: isLoadingSnapshots } = useQuery({
    queryKey: ['sites', siteId, 'snapshots'],
    queryFn: () => monitoringApi.listSnapshots(siteId, { page: 1, per_page: 30 }),
    enabled: !!siteId,
  })

  const { data: alertsData, isLoading: isLoadingAlerts } = useQuery({
    queryKey: ['sites', siteId, 'alerts'],
    queryFn: () => monitoringApi.listAlertsForSite(siteId, { page: 1, per_page: 20 }),
    enabled: !!siteId,
  })

  const monitoringMutation = useMutation({
    mutationFn: (enable: boolean) =>
      enable ? sitesApi.enableMonitoring(siteId) : sitesApi.disableMonitoring(siteId),
    onSuccess: (_, enable) => {
      toast({ title: enable ? 'Monitoring enabled' : 'Monitoring disabled' })
      queryClient.invalidateQueries({ queryKey: ['sites', siteId] })
    },
    onError: () => {
      toast({
        title: 'Failed to update monitoring',
        description: 'Please try again.',
        variant: 'destructive',
      })
    },
  })

  const acknowledgeMutation = useMutation({
    mutationFn: (alertId: string) => monitoringApi.acknowledgeAlert(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'alerts'] })
    },
  })

  if (isLoadingSite) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="p-6">
            <Skeleton className="h-[300px] w-full" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!site) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-medium mb-2">Site not found</h2>
        <Link href="/dashboard">
          <Button>Back to Dashboard</Button>
        </Link>
      </div>
    )
  }

  const snapshots = snapshotsData?.items ?? []
  const alerts = alertsData?.items ?? []
  const unacknowledgedAlerts = alerts.filter((a) => !a.acknowledged)

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href={`/sites/${siteId}`}
        className="inline-flex items-center gap-2 text-sm text-foreground-muted hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Site
      </Link>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-serif text-3xl font-medium">Monitoring</h1>
          <p className="text-foreground-muted mt-1">{site.name}</p>
        </div>
        <Button
          variant={site.monitoring_enabled ? 'outline' : 'default'}
          onClick={() => monitoringMutation.mutate(!site.monitoring_enabled)}
          disabled={monitoringMutation.isPending}
        >
          {monitoringMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : site.monitoring_enabled ? (
            <>
              <BellOff className="h-4 w-4 mr-2" />
              Disable Monitoring
            </>
          ) : (
            <>
              <Bell className="h-4 w-4 mr-2" />
              Enable Monitoring
            </>
          )}
        </Button>
      </div>

      {/* Status card */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div
                className={cn(
                  'h-3 w-3 rounded-full',
                  site.monitoring_enabled ? 'bg-green-400 animate-pulse' : 'bg-foreground-muted'
                )}
              />
              <div>
                <p className="font-medium">
                  {site.monitoring_enabled ? 'Monitoring Active' : 'Monitoring Disabled'}
                </p>
                <p className="text-sm text-foreground-muted">
                  {site.monitoring_enabled
                    ? `${snapshots.length} snapshots collected`
                    : 'Enable to start tracking score changes'}
                </p>
              </div>
            </div>
            {unacknowledgedAlerts.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/20 text-amber-400 text-sm">
                <AlertTriangle className="h-4 w-4" />
                {unacknowledgedAlerts.length} unread alert{unacknowledgedAlerts.length !== 1 ? 's' : ''}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Trend chart */}
      <Card>
        <CardHeader>
          <CardTitle>Score Trend</CardTitle>
          <CardDescription>Your findability score over time</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoadingSnapshots ? (
            <Skeleton className="h-[300px] w-full" />
          ) : snapshots.length === 0 ? (
            <div className="h-[300px] flex items-center justify-center text-foreground-muted">
              {site.monitoring_enabled
                ? 'No snapshots yet. Check back tomorrow.'
                : 'Enable monitoring to start collecting data.'}
            </div>
          ) : (
            <TrendChart snapshots={snapshots} height={300} />
          )}
        </CardContent>
      </Card>

      {/* Snapshot history */}
      <Card>
        <CardHeader>
          <CardTitle>Snapshot History</CardTitle>
          <CardDescription>Daily score snapshots</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoadingSnapshots ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : snapshots.length === 0 ? (
            <p className="text-center text-foreground-muted py-8">No snapshots yet.</p>
          ) : (
            <div className="space-y-2">
              {snapshots.slice(0, 10).map((snapshot, index) => {
                const prevSnapshot = snapshots[index + 1]
                const scoreDiff = prevSnapshot ? snapshot.score - prevSnapshot.score : null

                return (
                  <div
                    key={snapshot.id}
                    className="flex items-center justify-between p-3 rounded-lg border border-border/30"
                  >
                    <div className="flex items-center gap-4">
                      <GradeBadge grade={snapshot.grade} size="sm" />
                      <div>
                        <p className="font-medium font-mono">{snapshot.score}</p>
                        <p className="text-xs text-foreground-muted">
                          {format(new Date(snapshot.created_at), 'MMM d, yyyy')}
                        </p>
                      </div>
                    </div>
                    {scoreDiff !== null && scoreDiff !== 0 && (
                      <span
                        className={cn(
                          'text-sm font-medium',
                          scoreDiff > 0 ? 'text-green-400' : 'text-red-400'
                        )}
                      >
                        {scoreDiff > 0 ? '+' : ''}
                        {scoreDiff}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Alerts */}
      <Card>
        <CardHeader>
          <CardTitle>Alerts</CardTitle>
          <CardDescription>Notifications about significant changes</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoadingAlerts ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : alerts.length === 0 ? (
            <p className="text-center text-foreground-muted py-8">No alerts yet.</p>
          ) : (
            <div className="space-y-2">
              {alerts.map((alert) => (
                <AlertItem
                  key={alert.id}
                  alert={alert}
                  onAcknowledge={() => acknowledgeMutation.mutate(alert.id)}
                  isAcknowledging={acknowledgeMutation.isPending}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function AlertItem({
  alert,
  onAcknowledge,
  isAcknowledging,
}: {
  alert: Alert
  onAcknowledge: () => void
  isAcknowledging: boolean
}) {
  const severityStyles: Record<AlertSeverity, string> = {
    critical: 'border-red-500/30 bg-red-500/5',
    warning: 'border-amber-500/30 bg-amber-500/5',
    info: 'border-blue-500/30 bg-blue-500/5',
  }

  const severityIcons: Record<AlertSeverity, React.ReactNode> = {
    critical: <TrendingDown className="h-4 w-4 text-red-400" />,
    warning: <AlertTriangle className="h-4 w-4 text-amber-400" />,
    info: <Bell className="h-4 w-4 text-blue-400" />,
  }

  return (
    <div
      className={cn(
        'flex items-start justify-between p-4 rounded-lg border',
        severityStyles[alert.severity],
        alert.acknowledged && 'opacity-60'
      )}
    >
      <div className="flex items-start gap-3">
        {severityIcons[alert.severity]}
        <div>
          <p className="font-medium">{alert.message}</p>
          <p className="text-xs text-foreground-muted mt-1">
            {formatRelativeTime(alert.created_at)}
          </p>
        </div>
      </div>
      {!alert.acknowledged && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onAcknowledge}
          disabled={isAcknowledging}
        >
          {isAcknowledging ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
        </Button>
      )}
    </div>
  )
}
