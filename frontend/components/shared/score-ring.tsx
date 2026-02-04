'use client'

import { useEffect, useRef } from 'react'
import { cn, getGradeFromScore, getGradeColor } from '@/lib/utils'
import type { Grade } from '@/types'

interface ScoreRingProps {
  score: number
  size?: number
  strokeWidth?: number
  animate?: boolean
  showGrade?: boolean
  className?: string
}

export function ScoreRing({
  score,
  size = 120,
  strokeWidth = 8,
  animate = true,
  showGrade = true,
  className,
}: ScoreRingProps) {
  const circleRef = useRef<SVGCircleElement>(null)
  const grade = getGradeFromScore(score)

  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const targetOffset = circumference - (score / 100) * circumference

  // Get color based on grade
  const getStrokeColor = (grade: Grade): string => {
    const colors: Record<Grade, string> = {
      A: '#22d3ee', // cyan-400
      B: '#4ade80', // green-400
      C: '#fbbf24', // amber-400
      D: '#fb923c', // orange-400
      F: '#f87171', // red-400
    }
    return colors[grade]
  }

  useEffect(() => {
    if (animate && circleRef.current) {
      // Reset to initial state
      circleRef.current.style.strokeDashoffset = String(circumference)

      // Trigger animation
      requestAnimationFrame(() => {
        if (circleRef.current) {
          circleRef.current.style.strokeDashoffset = String(targetOffset)
        }
      })
    }
  }, [animate, circumference, targetOffset])

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-background-tertiary"
        />
        {/* Animated foreground circle */}
        <circle
          ref={circleRef}
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={getStrokeColor(grade)}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={animate ? circumference : targetOffset}
          style={{
            transition: animate ? 'stroke-dashoffset 1.5s ease-out' : 'none',
          }}
        />
      </svg>

      {/* Center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={cn(
            'font-mono text-3xl font-bold',
            getGradeColor(grade)
          )}
        >
          {score}
        </span>
        {showGrade && (
          <span className={cn('text-sm font-medium', getGradeColor(grade))}>
            Grade {grade}
          </span>
        )}
      </div>
    </div>
  )
}
