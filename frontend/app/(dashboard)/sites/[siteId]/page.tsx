'use client'

import Link from 'next/link'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, Play, Settings, Clock, Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { sitesApi, runsApi } from '@/lib/api'
import { toast } from '@/lib/hooks'
import { cn, formatRelativeTime, formatUrl, getStatusLabel } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScoreRing, GradeBadge, Skeleton } from '@/components/shared'
import { ActiveRunCard } from '@/components/site'
import type { Run } from '@/types'

interface SiteDetailPageProps {
  params: { siteId: string }
}

export default function SiteDetailPage({ params }: SiteDetailPageProps) {
  const { siteId } = params
  const queryClient = useQueryClient()

  const { data: site, isLoading: isLoadingSite } = useQuery({
    queryKey: ['sites', siteId],
    queryFn: () => sitesApi.get(siteId),
  })

  const { data: runsData, refetch: refetchRuns } = useQuery({
    queryKey: ['sites', siteId, 'runs'],
    queryFn: () => runsApi.list(siteId, { page: 1, per_page: 10 }),
    enabled: !!siteId,
    refetchInterval: (query) => {
      // Poll more frequently if there's an active run
      const runs = query.state.data?.items ?? []
      const hasActiveRun = runs.some(r => !['completed', 'failed'].includes(r.status))
      return hasActiveRun ? 5000 : false
    },
  })

  const startRunMutation = useMutation({
    mutationFn: () => runsApi.create(siteId),
    onSuccess: () => {
      toast({
        title: 'Run started',
        description: 'Your findability audit is in progress.',
      })
      queryClient.invalidateQueries({ queryKey: ['sites', siteId] })
      queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'runs'] })
    },
    onError: () => {
      toast({
        title: 'Failed to start run',
        description: 'Please try again.',
        variant: 'destructive',
      })
    },
  })

  const cancelRunMutation = useMutation({
    mutationFn: (runId: string) => runsApi.cancel(siteId, runId),
    onSuccess: () => {
      toast({
        title: 'Run cancelled',
        description: 'The audit has been stopped.',
      })
      queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'runs'] })
    },
  })

  const handleRunComplete = () => {
    queryClient.invalidateQueries({ queryKey: ['sites', siteId] })
    refetchRuns()
    toast({
      title: 'Audit complete',
      description: 'Your findability report is ready.',
      variant: 'success',
    })
  }

  if (isLoadingSite) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="p-8">
            <div className="flex flex-col md:flex-row items-center gap-8">
              <Skeleton className="h-[140px] w-[140px] rounded-full" />
              <div className="space-y-3 flex-1">
                <Skeleton className="h-8 w-64" />
                <Skeleton className="h-4 w-48" />
                <div className="flex gap-6 pt-4">
                  <Skeleton className="h-12 w-24" />
                  <Skeleton className="h-12 w-24" />
                  <Skeleton className="h-12 w-24" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {[1, 2, 3].map(i => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!site) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-medium mb-2">Site not found</h2>
        <p className="text-foreground-muted mb-4">This site doesn't exist or you don't have access to it.</p>
        <Link href="/dashboard">
          <Button>Back to Dashboard</Button>
        </Link>
      </div>
    )
  }

  const runs = runsData?.items ?? []
  const activeRun = runs.find(r => !['complete', 'failed'].includes(r.status))
  const completedRuns = runs.filter(r => r.status === 'complete')
  const latestCompletedRun = completedRuns[0]
  const previousCompletedRun = completedRuns[1]

  // Calculate score trend
  const scoreTrend = latestCompletedRun && previousCompletedRun
    ? (latestCompletedRun.score ?? 0) - (previousCompletedRun.score ?? 0)
    : null

  return (
    <div className="space-y-6">
      {/* Back link and header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-sm text-foreground-muted hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Link>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/sites/${siteId}/settings`}>
              <Settings className="h-4 w-4 mr-2" />
              Settings
            </Link>
          </Button>
          <Button
            size="sm"
            onClick={() => startRunMutation.mutate()}
            disabled={startRunMutation.isPending || !!activeRun}
          >
            {startRunMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Starting...
              </>
            ) : activeRun ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Run in Progress
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                New Run
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Site header card */}
      <Card>
        <CardContent className="p-6 md:p-8">
          <div className="flex flex-col md:flex-row items-start md:items-center gap-6 md:gap-8">
            {/* Score ring */}
            <div className="mx-auto md:mx-0">
              {site.latest_score !== null && site.latest_grade ? (
                <ScoreRing score={site.latest_score} size={140} />
              ) : (
                <div className="w-[140px] h-[140px] rounded-full bg-background-tertiary flex items-center justify-center">
                  <span className="text-foreground-muted text-sm text-center px-4">No score yet</span>
                </div>
              )}
            </div>

            {/* Site info */}
            <div className="flex-1 text-center md:text-left">
              <h1 className="font-serif text-2xl md:text-3xl font-medium mb-1">{site.name}</h1>
              <a
                href={`https://${site.domain}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-foreground-muted hover:text-primary transition-colors"
              >
                {site.domain}
                <ExternalLink className="h-3 w-3" />
              </a>

              {/* Score trend */}
              {scoreTrend !== null && (
                <div className="mt-2">
                  <span className={cn(
                    'inline-flex items-center gap-1 text-sm font-medium',
                    scoreTrend > 0 ? 'text-green-400' : scoreTrend < 0 ? 'text-red-400' : 'text-foreground-muted'
                  )}>
                    {scoreTrend > 0 ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : scoreTrend < 0 ? (
                      <TrendingDown className="h-4 w-4" />
                    ) : (
                      <Minus className="h-4 w-4" />
                    )}
                    {scoreTrend > 0 ? '+' : ''}{scoreTrend} pts from last run
                  </span>
                </div>
              )}

              {/* Quick stats */}
              <div className="flex items-center justify-center md:justify-start gap-6 mt-4">
                <div>
                  <p className="text-xs text-foreground-muted uppercase tracking-wider">Monitoring</p>
                  <p className={cn(
                    'text-sm font-medium',
                    site.monitoring_enabled ? 'text-green-400' : 'text-foreground-muted'
                  )}>
                    {site.monitoring_enabled ? 'Active' : 'Disabled'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-foreground-muted uppercase tracking-wider">Last Run</p>
                  <p className="text-sm font-medium">
                    {latestCompletedRun ? formatRelativeTime(latestCompletedRun.completed_at!) : 'Never'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-foreground-muted uppercase tracking-wider">Competitors</p>
                  <p className="text-sm font-medium">{site.competitor_count ?? 0}</p>
                </div>
              </div>
            </div>

            {/* View report button */}
            {latestCompletedRun?.report_id && (
              <div className="w-full md:w-auto">
                <Link href={`/reports/${latestCompletedRun.report_id}`} className="block">
                  <Button variant="outline" className="w-full md:w-auto">View Full Report</Button>
                </Link>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Active run card with SSE */}
      {activeRun && (
        <ActiveRunCard
          siteId={siteId}
          runId={activeRun.id}
          onComplete={handleRunComplete}
          onCancel={() => cancelRunMutation.mutate(activeRun.id)}
        />
      )}

      {/* Run history */}
      <Card>
        <CardHeader>
          <CardTitle>Run History</CardTitle>
        </CardHeader>
        <CardContent>
          {runs.length === 0 ? (
            <p className="text-center text-foreground-muted py-8">
              No runs yet. Start your first audit to see results here.
            </p>
          ) : (
            <div className="space-y-2">
              {runs.map((run) => (
                <RunHistoryItem key={run.id} run={run} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function RunHistoryItem({ run }: { run: Run }) {
  const isCompleted = run.status === 'complete'
  const isFailed = run.status === 'failed'
  const isRunning = !isCompleted && !isFailed

  return (
    <div className={cn(
      'flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-lg border gap-3',
      isRunning ? 'border-primary/30 bg-primary/5' : 'border-border/30'
    )}>
      <div className="flex items-center gap-4">
        {isCompleted && run.grade ? (
          <GradeBadge grade={run.grade} size="sm" />
        ) : isRunning ? (
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        ) : (
          <div className="h-6 w-6 rounded-full bg-red-500/20 flex items-center justify-center">
            <span className="text-red-400 text-xs">!</span>
          </div>
        )}
        <div>
          <p className="font-medium">
            {isCompleted ? `Score: ${run.score}` : isFailed ? 'Failed' : getStatusLabel(run.status)}
          </p>
          <p className="text-sm text-foreground-muted flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatRelativeTime(run.created_at)}
          </p>
        </div>
      </div>
      {isCompleted && run.report_id && (
        <Link href={`/reports/${run.report_id}`}>
          <Button variant="ghost" size="sm">View Report</Button>
        </Link>
      )}
      {isFailed && run.error_message && (
        <p className="text-xs text-red-400 sm:max-w-[200px] truncate" title={run.error_message}>
          {run.error_message}
        </p>
      )}
    </div>
  )
}
