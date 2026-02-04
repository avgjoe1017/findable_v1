'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Globe, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react'
import { sitesApi, runsApi } from '@/lib/api'
import { toast } from '@/lib/hooks'
import { StatCard, SitesTable } from '@/components/dashboard'
import { DashboardSkeleton } from '@/components/shared'

export default function DashboardPage() {
  const queryClient = useQueryClient()

  const { data: sitesData, isLoading: isLoadingSites } = useQuery({
    queryKey: ['sites'],
    queryFn: () => sitesApi.list({ page: 1, per_page: 50 }),
  })

  const startRunMutation = useMutation({
    mutationFn: (siteId: string) => runsApi.create(siteId),
    onSuccess: (run, siteId) => {
      toast({
        title: 'Run started',
        description: 'Your findability audit is in progress.',
      })
      queryClient.invalidateQueries({ queryKey: ['sites', siteId] })
    },
    onError: () => {
      toast({
        title: 'Failed to start run',
        description: 'Please try again.',
        variant: 'destructive',
      })
    },
  })

  const deleteSiteMutation = useMutation({
    mutationFn: (siteId: string) => sitesApi.delete(siteId),
    onSuccess: () => {
      toast({
        title: 'Site deleted',
        description: 'The site has been removed.',
      })
      queryClient.invalidateQueries({ queryKey: ['sites'] })
    },
    onError: () => {
      toast({
        title: 'Failed to delete site',
        description: 'Please try again.',
        variant: 'destructive',
      })
    },
  })

  const handleStartRun = (siteId: string) => {
    startRunMutation.mutate(siteId)
  }

  const handleDeleteSite = (siteId: string) => {
    if (confirm('Are you sure you want to delete this site? This action cannot be undone.')) {
      deleteSiteMutation.mutate(siteId)
    }
  }

  if (isLoadingSites) {
    return <DashboardSkeleton />
  }

  const sites = sitesData?.items ?? []

  // Calculate stats
  const totalSites = sites.length
  const avgScore = sites.length > 0
    ? Math.round(sites.reduce((sum, s) => sum + (s.latest_score ?? 0), 0) / sites.filter(s => s.latest_score !== null).length) || 0
    : 0
  const sitesWithAlerts = sites.filter(s => s.latest_score !== null && s.latest_score < 60).length
  const sitesMonitored = sites.filter(s => s.monitoring_enabled).length

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="font-serif text-3xl font-medium">Dashboard</h1>
        <p className="text-foreground-muted mt-1">
          Monitor your sites' AI findability across all major answer engines.
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Sites"
          value={totalSites}
          description="Sites being tracked"
          icon={Globe}
        />
        <StatCard
          title="Average Score"
          value={avgScore}
          description="Across all sites"
          icon={TrendingUp}
          trend={avgScore > 0 ? { value: 5, isPositive: true } : undefined}
        />
        <StatCard
          title="Needs Attention"
          value={sitesWithAlerts}
          description="Sites scoring below 60"
          icon={AlertTriangle}
        />
        <StatCard
          title="Monitoring Active"
          value={sitesMonitored}
          description="Sites with daily checks"
          icon={CheckCircle}
        />
      </div>

      {/* Sites table */}
      <SitesTable
        sites={sites}
        onStartRun={handleStartRun}
        onDelete={handleDeleteSite}
      />
    </div>
  )
}
