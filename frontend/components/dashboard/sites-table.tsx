'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowUpDown, ExternalLink, MoreVertical, Play, Trash2 } from 'lucide-react'
import { cn, formatRelativeTime, formatUrl } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { GradeBadge } from '@/components/shared'
import type { Site } from '@/types'

interface SitesTableProps {
  sites: Site[]
  isLoading?: boolean
  onStartRun?: (siteId: string) => void
  onDelete?: (siteId: string) => void
}

export function SitesTable({ sites, isLoading, onStartRun, onDelete }: SitesTableProps) {
  const [sortBy, setSortBy] = useState<'name' | 'latest_score' | 'created_at'>('latest_score')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  const handleSort = (column: typeof sortBy) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(column)
      setSortOrder('desc')
    }
  }

  const sortedSites = [...sites].sort((a, b) => {
    let comparison = 0
    switch (sortBy) {
      case 'name':
        comparison = (a.name ?? '').localeCompare(b.name ?? '')
        break
      case 'latest_score':
        comparison = (a.latest_score ?? 0) - (b.latest_score ?? 0)
        break
      case 'created_at':
        comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        break
    }
    return sortOrder === 'asc' ? comparison : -comparison
  })

  const SortButton = ({ column, children }: { column: typeof sortBy; children: React.ReactNode }) => (
    <button
      onClick={() => handleSort(column)}
      className={cn(
        'flex items-center gap-1 text-xs font-medium uppercase tracking-wider',
        sortBy === column ? 'text-primary' : 'text-foreground-muted hover:text-foreground'
      )}
    >
      {children}
      <ArrowUpDown className="h-3 w-3" />
    </button>
  )

  if (isLoading) {
    return (
      <Card>
        <div className="p-6 border-b border-border/30">
          <h2 className="font-serif text-lg font-medium">Your Sites</h2>
        </div>
        <div className="p-8 text-center text-foreground-muted">
          Loading sites...
        </div>
      </Card>
    )
  }

  if (sites.length === 0) {
    return (
      <Card>
        <div className="p-6 border-b border-border/30">
          <h2 className="font-serif text-lg font-medium">Your Sites</h2>
        </div>
        <div className="p-8 text-center">
          <p className="text-foreground-muted mb-4">No sites yet. Add your first site to get started.</p>
          <Link href="/sites/new">
            <Button>Add Your First Site</Button>
          </Link>
        </div>
      </Card>
    )
  }

  return (
    <Card>
      <div className="p-6 border-b border-border/30 flex items-center justify-between">
        <h2 className="font-serif text-lg font-medium">Your Sites</h2>
        <Link href="/sites/new">
          <Button size="sm">Add Site</Button>
        </Link>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border/30 bg-background-secondary/50">
              <th className="px-4 py-3 text-left">
                <SortButton column="name">Site</SortButton>
              </th>
              <th className="px-4 py-3 text-left">
                <SortButton column="latest_score">Score</SortButton>
              </th>
              <th className="px-4 py-3 text-left">
                <span className="text-xs font-medium uppercase tracking-wider text-foreground-muted">Grade</span>
              </th>
              <th className="px-4 py-3 text-left">
                <span className="text-xs font-medium uppercase tracking-wider text-foreground-muted">Monitoring</span>
              </th>
              <th className="px-4 py-3 text-left">
                <SortButton column="created_at">Added</SortButton>
              </th>
              <th className="px-4 py-3 text-right">
                <span className="text-xs font-medium uppercase tracking-wider text-foreground-muted">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedSites.map((site) => (
              <tr key={site.id} className="border-b border-border/30 hover:bg-card-hover/50 transition-colors">
                <td className="px-4 py-3">
                  <Link href={`/sites/${site.id}`} className="block group">
                    <p className="font-medium group-hover:text-primary transition-colors">{site.name}</p>
                    <p className="text-sm text-foreground-muted flex items-center gap-1">
                      {site.domain}
                      <ExternalLink className="h-3 w-3" />
                    </p>
                  </Link>
                </td>
                <td className="px-4 py-3">
                  {site.latest_score !== null ? (
                    <span className="font-mono text-lg font-bold">{site.latest_score}</span>
                  ) : (
                    <span className="text-foreground-muted">--</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {site.latest_grade ? (
                    <GradeBadge grade={site.latest_grade} size="sm" />
                  ) : (
                    <span className="text-foreground-muted">--</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={cn(
                    'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
                    site.monitoring_enabled
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-foreground-muted/20 text-foreground-muted'
                  )}>
                    <span className={cn(
                      'h-1.5 w-1.5 rounded-full',
                      site.monitoring_enabled ? 'bg-green-400' : 'bg-foreground-muted'
                    )} />
                    {site.monitoring_enabled ? 'Active' : 'Off'}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-foreground-muted">
                  {formatRelativeTime(site.created_at)}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onStartRun?.(site.id)}
                      title="Start new run"
                    >
                      <Play className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => onDelete?.(site.id)}
                      className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                      title="Delete site"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
