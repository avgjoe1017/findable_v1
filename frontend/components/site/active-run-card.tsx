'use client'

import { useEffect, useState } from 'react'
import { Loader2, RefreshCw, XCircle } from 'lucide-react'
import { useRunProgress, getProgressPercent } from '@/lib/hooks'
import { cn, getStatusLabel } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'

interface ActiveRunCardProps {
  siteId: string
  runId: string
  onComplete?: () => void
  onCancel?: () => void
}

export function ActiveRunCard({ siteId, runId, onComplete, onCancel }: ActiveRunCardProps) {
  const { progress, isConnected, error, reconnect } = useRunProgress(siteId, runId, {
    onComplete,
  })

  const [showShimmer, setShowShimmer] = useState(true)

  // Disable shimmer after animation completes
  useEffect(() => {
    const timer = setTimeout(() => setShowShimmer(false), 3000)
    return () => clearTimeout(timer)
  }, [])

  const progressPercent = getProgressPercent(progress)
  const statusLabel = progress ? getStatusLabel(progress.status) : 'Starting...'

  return (
    <Card className={cn(
      'relative overflow-hidden border-primary/50',
      showShimmer && 'before:absolute before:inset-0 before:bg-shimmer-gradient before:bg-[length:200%_100%] before:animate-shimmer'
    )}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            Audit in Progress
          </span>
          {!isConnected && !error && (
            <span className="text-xs text-amber-400 flex items-center gap-1">
              <RefreshCw className="h-3 w-3 animate-spin" />
              Reconnecting...
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <div className="flex items-center justify-between p-3 rounded-lg bg-red-500/10 border border-red-500/30">
            <div className="flex items-center gap-2 text-red-400">
              <XCircle className="h-4 w-4" />
              <span className="text-sm">{error}</span>
            </div>
            <Button variant="ghost" size="sm" onClick={reconnect}>
              Retry
            </Button>
          </div>
        ) : (
          <>
            {/* Progress bar */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-foreground-muted">{statusLabel}</span>
                <span className="font-mono text-foreground-muted">{progressPercent}%</span>
              </div>
              <Progress value={progressPercent} className="h-2" />
            </div>

            {/* Step details */}
            {progress?.current_step && (
              <p className="text-xs text-foreground-muted">{progress.current_step}</p>
            )}

            {/* Page progress */}
            {progress?.pages_crawled !== undefined && progress?.pages_total !== undefined && (
              <div className="flex items-center gap-4 text-xs text-foreground-muted">
                <span>Pages: {progress.pages_crawled} / {progress.pages_total}</span>
              </div>
            )}

            {/* Cancel button */}
            {onCancel && (
              <div className="pt-2">
                <Button variant="ghost" size="sm" onClick={onCancel} className="text-foreground-muted">
                  Cancel Run
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
