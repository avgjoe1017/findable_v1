'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { runsApi } from '@/lib/api'
import type { RunProgress, RunStatus } from '@/types'

interface UseRunProgressOptions {
  onComplete?: () => void
  onError?: (error: string) => void
}

interface UseRunProgressReturn {
  progress: RunProgress | null
  isConnected: boolean
  error: string | null
  reconnect: () => void
}

const INITIAL_PROGRESS: RunProgress = {
  status: 'pending',
  progress: 0,
  message: 'Queued...',
}

export function useRunProgress(
  siteId: string | undefined,
  runId: string | undefined,
  options: UseRunProgressOptions = {}
): UseRunProgressReturn {
  const [progress, setProgress] = useState<RunProgress | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const eventSourceRef = useRef<EventSource | null>(null)
  const retryCountRef = useRef(0)
  const maxRetries = 5

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsConnected(false)
  }, [])

  const connect = useCallback(() => {
    if (!siteId || !runId) return

    cleanup()
    setError(null)

    try {
      const eventSource = runsApi.createProgressStream(siteId, runId)
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        setIsConnected(true)
        retryCountRef.current = 0
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as RunProgress
          setProgress(data)

          // Check for terminal states
          if (data.status === 'complete') {
            options.onComplete?.()
            // Invalidate run and site queries to refresh data
            queryClient.invalidateQueries({ queryKey: ['runs', runId] })
            queryClient.invalidateQueries({ queryKey: ['sites', siteId] })
            cleanup()
          } else if (data.status === 'failed') {
            options.onError?.(data.message || 'Run failed')
            queryClient.invalidateQueries({ queryKey: ['runs', runId] })
            cleanup()
          }
        } catch (e) {
          console.error('Failed to parse SSE message:', e)
        }
      }

      eventSource.onerror = () => {
        setIsConnected(false)

        // Attempt reconnect with backoff
        if (retryCountRef.current < maxRetries) {
          retryCountRef.current++
          const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000)
          setTimeout(connect, delay)
        } else {
          setError('Connection lost. Please refresh the page.')
          cleanup()
        }
      }
    } catch (e) {
      console.error('Failed to create EventSource:', e)
      setError('Failed to connect to progress stream')
    }
  }, [siteId, runId, cleanup, options, queryClient])

  const reconnect = useCallback(() => {
    retryCountRef.current = 0
    connect()
  }, [connect])

  // Connect when IDs are available
  useEffect(() => {
    if (siteId && runId) {
      setProgress(INITIAL_PROGRESS)
      connect()
    }

    return cleanup
  }, [siteId, runId, connect, cleanup])

  return {
    progress,
    isConnected,
    error,
    reconnect,
  }
}

/**
 * Helper to check if a status is a "running" state
 */
export function isRunningStatus(status: RunStatus): boolean {
  return !['complete', 'failed'].includes(status)
}

/**
 * Get progress percentage from run progress
 */
export function getProgressPercent(progress: RunProgress | null): number {
  if (!progress) return 0

  const statusProgress: Partial<Record<RunStatus, number>> = {
    queued: 0,
    pending: 5,
    crawling: 15,
    extracting: 35,
    chunking: 50,
    embedding: 65,
    simulating: 75,
    scoring: 80,
    generating_questions: 85,
    generating_fixes: 90,
    assembling: 95,
    complete: 100,
    failed: 0,
  }

  // Use explicit progress if available, otherwise use status-based estimate
  if (progress.progress > 0) {
    return progress.progress
  }

  return statusProgress[progress.status] ?? 0
}
