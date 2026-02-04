'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, ChevronDown, ChevronUp, Check, X, AlertTriangle } from 'lucide-react'
import { runsApi } from '@/lib/api'
import { cn, formatDate, formatUrl, getSeverityColor } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { ScoreRing, GradeBadge, Skeleton } from '@/components/shared'
import { ShowTheMath } from '@/components/report'
import type { Fix, CategoryScore } from '@/types'

interface ReportPageProps {
  params: { reportId: string }
}

export default function ReportPage({ params }: ReportPageProps) {
  const { reportId } = params

  const { data: report, isLoading, error } = useQuery({
    queryKey: ['reports', reportId],
    queryFn: () => runsApi.getReport(reportId),
  })

  // Debug logging
  console.log('Report page state:', { reportId, isLoading, error, hasReport: !!report })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="p-8">
            <div className="flex items-center gap-8">
              <Skeleton className="h-40 w-40 rounded-full" />
              <div className="space-y-3">
                <Skeleton className="h-8 w-64" />
                <Skeleton className="h-4 w-48" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-medium mb-2">Error loading report</h2>
        <p className="text-foreground-muted mb-4">{error instanceof Error ? error.message : 'Unknown error'}</p>
        <Link href="/dashboard">
          <Button>Back to Dashboard</Button>
        </Link>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-medium mb-2">Report not found</h2>
        <p className="text-foreground-muted mb-4">This report doesn't exist or is still processing.</p>
        <Link href="/dashboard">
          <Button>Back to Dashboard</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Back link */}
      <Link
        href={`/sites/${report.site_id}`}
        className="inline-flex items-center gap-2 text-sm text-foreground-muted hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Site
      </Link>

      {/* Hero section */}
      <Card>
        <CardContent className="p-8">
          <div className="flex flex-col lg:flex-row items-start lg:items-center gap-8">
            {/* Score ring */}
            <ScoreRing score={report.score} size={160} animate />

            {/* Report info */}
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <h1 className="font-serif text-3xl font-medium">{report.name}</h1>
                <GradeBadge grade={report.grade} size="lg" />
              </div>
              <a
                href={report.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-foreground-muted hover:text-primary transition-colors mb-4"
              >
                {formatUrl(report.url)}
                <ExternalLink className="h-3 w-3" />
              </a>

              {/* Summary */}
              <div className="space-y-2">
                <p className="text-lg">{report.summary.headline}</p>
                <p className="text-foreground-muted">{report.summary.description}</p>
              </div>

              {/* Key findings */}
              {report.summary.key_findings.length > 0 && (
                <ul className="mt-4 space-y-1">
                  {report.summary.key_findings.map((finding, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-foreground-muted">
                      <span className="text-primary mt-0.5">•</span>
                      {finding}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Report date */}
            <div className="text-right">
              <p className="text-xs text-foreground-muted uppercase tracking-wider">Generated</p>
              <p className="text-sm">{formatDate(report.created_at)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Signal stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatBox label="Pages Crawled" value={report.signals.pages_crawled} />
        <StatBox label="Chunks Created" value={report.signals.chunks_created} />
        <StatBox
          label="Questions Answered"
          value={`${report.signals.questions_answered}/${report.signals.questions_total}`}
        />
        <StatBox
          label="Answer Rate"
          value={`${Math.round((report.signals.questions_answered / report.signals.questions_total) * 100)}%`}
        />
        <StatBox label="Avg Retrieval Rank" value={report.signals.avg_retrieval_rank.toFixed(1)} />
      </div>

      {/* Category breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Score Breakdown</CardTitle>
          <CardDescription>
            How your score is calculated across key dimensions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {report.categories.map((category) => (
              <CategoryBar key={category.slug} category={category} />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Robustness bands */}
      <Card>
        <CardHeader>
          <CardTitle>Robustness Analysis</CardTitle>
          <CardDescription>
            Your score at different context window sizes
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {Object.entries(report.robustness).map(([band, result]) => (
              <div key={band} className="text-center p-4 rounded-lg bg-background-secondary/50">
                <p className="text-xs text-foreground-muted uppercase tracking-wider mb-2 capitalize">
                  {band}
                </p>
                <div className="flex items-center justify-center gap-3">
                  <span className="font-mono text-3xl font-bold">{result.score}</span>
                  <GradeBadge grade={result.grade} size="sm" />
                </div>
                <p className="text-xs text-foreground-muted mt-2">
                  {result.context_budget.toLocaleString()} tokens • {result.questions_answered} answered
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Show the math */}
      <ShowTheMath report={report} />

      {/* Fixes */}
      <Card>
        <CardHeader>
          <CardTitle>Recommended Fixes</CardTitle>
          <CardDescription>
            Actions to improve your findability score
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {report.fixes.length === 0 ? (
              <p className="text-center text-foreground-muted py-8">
                No fixes needed - your site is well optimized!
              </p>
            ) : (
              report.fixes.map((fix) => (
                <FixAccordion key={fix.id} fix={fix} />
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Crawled Pages */}
      {report.crawl && report.crawl.pages.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Crawled Pages ({report.crawl.total_pages})</CardTitle>
            <CardDescription>
              {report.crawl.total_words.toLocaleString()} words extracted • {report.crawl.total_chunks} chunks created • {report.crawl.urls_discovered.toLocaleString()} URLs discovered
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 max-h-[400px] overflow-y-auto">
              {report.crawl.pages.map((page, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-2 rounded text-sm hover:bg-background-secondary/50"
                >
                  <div className="flex-1 min-w-0 mr-4">
                    <a
                      href={page.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline truncate block"
                      title={page.url}
                    >
                      {page.title || page.url}
                    </a>
                    <p className="text-xs text-foreground-muted truncate">{page.url}</p>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-foreground-muted shrink-0">
                    <span title="Words">{page.word_count.toLocaleString()} words</span>
                    <span title="Chunks">{page.chunk_count} chunks</span>
                    <span title="Depth">depth {page.depth}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Questions breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Question Results</CardTitle>
          <CardDescription>
            How well your content answers each test question
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {report.questions.map((q, i) => (
              <div
                key={i}
                className={cn(
                  'flex items-start gap-3 p-3 rounded-lg',
                  q.answered ? 'bg-green-500/5' : 'bg-red-500/5'
                )}
              >
                <div className={cn(
                  'mt-0.5 h-5 w-5 rounded-full flex items-center justify-center',
                  q.answered ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                )}>
                  {q.answered ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{q.question}</p>
                  <div className="flex items-center gap-4 mt-1 text-xs text-foreground-muted">
                    <span className="capitalize">{q.question_type}</span>
                    {q.answered && q.retrieval_rank && (
                      <span>Rank #{q.retrieval_rank}</span>
                    )}
                    {q.confidence !== null && (
                      <span>Confidence: {Math.round(q.confidence * 100)}%</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardContent className="p-4 text-center">
        <p className="text-xs text-foreground-muted uppercase tracking-wider mb-1">{label}</p>
        <p className="font-mono text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  )
}

function CategoryBar({ category }: { category: CategoryScore }) {
  const percentage = Math.round(category.score * 100)

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">{category.name}</p>
          <p className="text-xs text-foreground-muted">{category.description}</p>
        </div>
        <div className="text-right">
          <span className="font-mono text-lg font-bold">{percentage}</span>
          <span className="text-foreground-muted text-sm">/100</span>
        </div>
      </div>
      <Progress value={percentage} />
    </div>
  )
}

function FixAccordion({ fix }: { fix: Fix }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className={cn(
      'border rounded-lg overflow-hidden',
      getSeverityColor(fix.severity)
    )}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-4 w-4" />
          <div>
            <p className="font-medium">{fix.title}</p>
            <p className="text-sm opacity-80">{fix.category}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm font-mono">+{fix.impact_estimate} pts</span>
          {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </div>
      </button>
      {isOpen && (
        <div className="px-4 pb-4 space-y-3">
          <p className="text-sm">{fix.description}</p>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider mb-1 opacity-70">Implementation</p>
            <p className="text-sm">{fix.implementation}</p>
          </div>
          {fix.affected_questions.length > 0 && (
            <div>
              <p className="text-xs font-medium uppercase tracking-wider mb-1 opacity-70">
                Affects {fix.affected_questions.length} questions
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
