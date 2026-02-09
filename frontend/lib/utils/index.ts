import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { Grade, FixSeverity, RunStatus } from '@/types'

/**
 * Merge Tailwind classes with clsx
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Get grade from numeric score
 */
export function getGradeFromScore(score: number): Grade {
  if (score >= 90) return 'A'
  if (score >= 75) return 'B'
  if (score >= 60) return 'C'
  if (score >= 40) return 'D'
  return 'F'
}

/**
 * Get grade color class
 */
export function getGradeColor(grade: Grade): string {
  const colors: Record<Grade, string> = {
    A: 'text-grade-a',
    B: 'text-grade-b',
    C: 'text-grade-c',
    D: 'text-grade-d',
    F: 'text-grade-f',
  }
  return colors[grade]
}

/**
 * Get grade background color class
 */
export function getGradeBgColor(grade: Grade): string {
  const colors: Record<Grade, string> = {
    A: 'bg-cyan-500/20 border-cyan-500/30',
    B: 'bg-green-500/20 border-green-500/30',
    C: 'bg-amber-500/20 border-amber-500/30',
    D: 'bg-orange-500/20 border-orange-500/30',
    F: 'bg-red-500/20 border-red-500/30',
  }
  return colors[grade]
}

/**
 * Get severity color class
 */
export function getSeverityColor(severity: FixSeverity): string {
  const colors: Record<FixSeverity, string> = {
    critical: 'text-red-400 bg-red-500/20 border-red-500/30',
    high: 'text-orange-400 bg-orange-500/20 border-orange-500/30',
    medium: 'text-amber-400 bg-amber-500/20 border-amber-500/30',
    low: 'text-blue-400 bg-blue-500/20 border-blue-500/30',
  }
  return colors[severity]
}

/**
 * Get run status label
 */
export function getStatusLabel(status: RunStatus): string {
  const labels: Record<RunStatus, string> = {
    queued: 'Queued',
    pending: 'Pending',
    crawling: 'Crawling pages...',
    extracting: 'Extracting content...',
    chunking: 'Creating chunks...',
    embedding: 'Generating embeddings...',
    simulating: 'Running simulation...',
    scoring: 'Calculating score...',
    generating_questions: 'Generating questions...',
    generating_fixes: 'Generating fixes...',
    assembling: 'Assembling report...',
    complete: 'Completed',
    failed: 'Failed',
  }
  return labels[status] || status
}

/**
 * Format date to relative time
 */
export function formatRelativeTime(date: string | Date): string {
  const now = new Date()
  const then = new Date(date)
  const diffMs = now.getTime() - then.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffSec < 60) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHour < 24) return `${diffHour}h ago`
  if (diffDay < 7) return `${diffDay}d ago`

  return then.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: then.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
}

/**
 * Format date to full format
 */
export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * Format URL for display (remove protocol, trailing slash)
 */
export function formatUrl(url: string): string {
  return url
    .replace(/^https?:\/\//, '')
    .replace(/\/$/, '')
}

/**
 * Format number with commas
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num)
}

/**
 * Format percentage
 */
export function formatPercent(num: number, decimals = 0): string {
  return `${num.toFixed(decimals)}%`
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 3)}...`
}

/**
 * Generate initials from name or email
 */
export function getInitials(nameOrEmail: string): string {
  const name = nameOrEmail.includes('@')
    ? nameOrEmail.split('@')[0]
    : nameOrEmail

  const parts = name.split(/[\s._-]+/)
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  }
  return name.slice(0, 2).toUpperCase()
}

/**
 * Calculate score ring circumference offset
 */
export function getScoreRingOffset(score: number, circumference = 314): number {
  return circumference - (score / 100) * circumference
}
