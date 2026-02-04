'use client'

import { cn, getGradeColor, getGradeBgColor } from '@/lib/utils'
import type { Grade } from '@/types'

interface GradeBadgeProps {
  grade: Grade
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function GradeBadge({ grade, size = 'md', className }: GradeBadgeProps) {
  const sizeClasses = {
    sm: 'w-6 h-6 text-xs',
    md: 'w-8 h-8 text-sm',
    lg: 'w-12 h-12 text-lg',
  }

  return (
    <div
      className={cn(
        'inline-flex items-center justify-center rounded-full border font-mono font-bold',
        sizeClasses[size],
        getGradeColor(grade),
        getGradeBgColor(grade),
        className
      )}
    >
      {grade}
    </div>
  )
}
