'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, Calculator, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { Report, CategoryScore, RobustnessResults } from '@/types'

interface ShowTheMathProps {
  report: Report
}

export function ShowTheMath({ report }: ShowTheMathProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  // Calculate weighted score breakdown
  const totalWeight = report.categories.reduce((sum, c) => sum + c.weight, 0)
  const categoryContributions = report.categories.map((category) => ({
    ...category,
    contribution: (category.score * category.weight) / totalWeight,
    percentage: (category.weight / totalWeight) * 100,
  }))

  const answeredRate = report.signals.questions_answered / report.signals.questions_total

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calculator className="h-5 w-5 text-primary" />
            <CardTitle>Show the Math</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? (
              <>
                <ChevronUp className="h-4 w-4 mr-1" />
                Hide
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4 mr-1" />
                Show
              </>
            )}
          </Button>
        </div>
        <CardDescription>
          Transparent breakdown of how your score is calculated
        </CardDescription>
      </CardHeader>

      {isExpanded && (
        <CardContent className="space-y-6">
          {/* Formula explanation */}
          <div className="p-4 rounded-lg bg-background-secondary/50 border border-border/30">
            <h4 className="font-medium mb-2 flex items-center gap-2">
              <Info className="h-4 w-4 text-primary" />
              Score Formula
            </h4>
            <p className="text-sm text-foreground-muted mb-3">
              Your Findable Score is calculated using a weighted average of six key dimensions,
              each measuring a different aspect of AI answer engine compatibility.
            </p>
            <code className="block p-3 rounded bg-background text-sm font-mono text-primary">
              Score = Σ(Category Score × Weight) / Total Weight
            </code>
          </div>

          {/* Category breakdown */}
          <div>
            <h4 className="font-medium mb-3">Category Contributions</h4>
            <div className="space-y-3">
              {categoryContributions.map((category) => (
                <div key={category.slug} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span>{category.name}</span>
                    <span className="font-mono">
                      {Math.round(category.score * 100)} × {category.percentage.toFixed(0)}% = {' '}
                      <span className="text-primary">{(category.contribution * 100).toFixed(1)}</span>
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-background-tertiary overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary transition-all duration-500"
                      style={{ width: `${category.score * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Total */}
            <div className="mt-4 pt-4 border-t border-border/30 flex items-center justify-between">
              <span className="font-medium">Final Score</span>
              <span className="font-mono text-lg">
                {categoryContributions
                  .reduce((sum, c) => sum + c.contribution * 100, 0)
                  .toFixed(0)} ≈{' '}
                <span className="text-primary font-bold">{report.score}</span>
              </span>
            </div>
          </div>

          {/* Robustness explanation */}
          <div>
            <h4 className="font-medium mb-3">Robustness Analysis</h4>
            <p className="text-sm text-foreground-muted mb-3">
              We test your content at three different context window sizes to ensure
              consistent retrieval across different AI model configurations.
            </p>
            <div className="grid grid-cols-3 gap-3">
              <RobustnessBox
                label="Conservative"
                tokens={3000}
                result={report.robustness.conservative}
              />
              <RobustnessBox
                label="Typical"
                tokens={6000}
                result={report.robustness.typical}
                highlight
              />
              <RobustnessBox
                label="Generous"
                tokens={12000}
                result={report.robustness.generous}
              />
            </div>
          </div>

          {/* Question suite breakdown */}
          <div>
            <h4 className="font-medium mb-3">Question Suite</h4>
            <p className="text-sm text-foreground-muted mb-3">
              Your site was tested against {report.signals.questions_total} questions
              across three categories.
            </p>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 rounded-lg bg-background-secondary/50">
                <p className="text-2xl font-mono font-bold">15</p>
                <p className="text-xs text-foreground-muted">Universal</p>
              </div>
              <div className="p-3 rounded-lg bg-background-secondary/50">
                <p className="text-2xl font-mono font-bold">5</p>
                <p className="text-xs text-foreground-muted">Site-Derived</p>
              </div>
              <div className="p-3 rounded-lg bg-background-secondary/50">
                <p className="text-2xl font-mono font-bold">
                  {report.signals.questions_total - 20}
                </p>
                <p className="text-xs text-foreground-muted">Custom</p>
              </div>
            </div>
            <div className="mt-3 p-3 rounded-lg bg-primary/10 border border-primary/30">
              <p className="text-sm">
                <span className="font-mono font-bold text-primary">
                  {(answeredRate * 100).toFixed(0)}%
                </span>{' '}
                of questions were answerable from your content
                ({report.signals.questions_answered} / {report.signals.questions_total})
              </p>
            </div>
          </div>

          {/* Retrieval stats */}
          <div>
            <h4 className="font-medium mb-3">Retrieval Statistics</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatBox label="Pages Crawled" value={report.signals.pages_crawled} />
              <StatBox label="Chunks Created" value={report.signals.chunks_created} />
              <StatBox
                label="Avg Chunk Size"
                value={`~${Math.round(report.signals.chunks_created > 0 ? 500 : 0)}`}
                suffix="tokens"
              />
              <StatBox
                label="Avg Retrieval Rank"
                value={report.signals.avg_retrieval_rank.toFixed(1)}
                suffix={report.signals.avg_retrieval_rank <= 3 ? '(good)' : '(needs work)'}
              />
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}

function RobustnessBox({
  label,
  tokens,
  result,
  highlight = false,
}: {
  label: string
  tokens: number
  result: RobustnessResults[keyof RobustnessResults]
  highlight?: boolean
}) {
  return (
    <div
      className={cn(
        'p-3 rounded-lg text-center',
        highlight
          ? 'bg-primary/10 border border-primary/30'
          : 'bg-background-secondary/50 border border-border/30'
      )}
    >
      <p className="text-xs text-foreground-muted uppercase tracking-wider mb-1">{label}</p>
      <p className="text-xl font-mono font-bold">{result.score}</p>
      <p className="text-xs text-foreground-muted">
        {tokens.toLocaleString()} tokens
      </p>
      <p className="text-xs text-foreground-muted">
        {result.questions_answered} answered
      </p>
    </div>
  )
}

function StatBox({
  label,
  value,
  suffix,
}: {
  label: string
  value: string | number
  suffix?: string
}) {
  return (
    <div className="p-3 rounded-lg bg-background-secondary/50 text-center">
      <p className="text-xs text-foreground-muted mb-1">{label}</p>
      <p className="font-mono font-bold">
        {value}
        {suffix && <span className="text-xs text-foreground-muted ml-1">{suffix}</span>}
      </p>
    </div>
  )
}
