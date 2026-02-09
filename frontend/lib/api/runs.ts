import { apiClient } from './client'
import type { Run, Report, CreateRunRequest, PaginatedResponse, Grade, CategoryScore, Fix, QuestionResult, RobustnessResults, CrawlInfo, CrawledPage } from '@/types'

// Backend report structure (nested)
interface BackendReport {
  metadata: {
    report_id: string
    site_id: string
    run_id: string
    company_name: string
    domain: string
    created_at: string
  }
  score: {
    total_score: number
    grade: string
    grade_description: string
    category_scores: Record<string, number>
    category_breakdown: Record<string, { score: number; weight: number; description?: string }>
    total_questions: number
    questions_answered: number
    questions_partial: number
    questions_unanswered: number
    coverage_percentage: number
    show_the_math: string
    criterion_scores?: Array<{ name: string; score: number; weight: number }>
  }
  fixes: {
    total_fixes: number
    critical_fixes: number
    fixes: Array<{
      id: string
      reason_code: string
      title: string
      description: string
      scaffold: string
      priority: number
      estimated_impact: { min: number; max: number; expected: number }
      effort_level: string
      target_url: string | null
      affected_questions: string[]
      affected_categories: string[]
    }>
  }
  crawl?: {
    total_pages: number
    total_words: number
    total_chunks: number
    urls_discovered: number
    urls_failed: number
    max_depth_reached: number
    duration_seconds: number
    pages: Array<{
      url: string
      title: string | null
      status_code: number
      depth: number
      word_count: number
      chunk_count: number
    }>
  }
}

// Transform backend report to frontend format
function transformReport(backend: BackendReport): Report {
  const categoryNames: Record<string, string> = {
    coverage: 'Coverage',
    extractability: 'Extractability',
    citability: 'Citability',
    trust: 'Trust',
    conflicts: 'Conflicts',
    redundancy: 'Redundancy',
  }

  const categoryDescriptions: Record<string, string> = {
    coverage: 'How many questions can be answered from your content',
    extractability: 'How easily AI can extract relevant information',
    citability: 'How quotable and attributable your content is',
    trust: 'Signals of legitimacy and authority',
    conflicts: 'Contradictions in your content',
    redundancy: 'Boilerplate crowding out useful content',
  }

  // Build categories array from category_scores
  const categories: CategoryScore[] = Object.entries(backend.score.category_scores ?? {}).map(([slug, score]) => ({
    name: categoryNames[slug] || slug,
    slug,
    score: (score ?? 0) / 100, // Convert to 0-1 scale for progress bars
    weight: backend.score.category_breakdown?.[slug]?.weight ?? 1,
    description: categoryDescriptions[slug] || '',
  }))

  // Transform fixes
  const fixes: Fix[] = (backend.fixes?.fixes ?? []).map(f => ({
    id: f.id,
    category: f.affected_categories?.[0] || 'general',
    severity: f.priority <= 1 ? 'critical' : f.priority <= 2 ? 'high' : f.priority <= 3 ? 'medium' : 'low',
    title: f.title,
    description: f.description,
    impact_estimate: f.estimated_impact?.expected ?? 0,
    implementation: f.scaffold,
    affected_questions: f.affected_questions ?? [],
  }))

  // Build question results (simplified - would need full sim data for complete results)
  const questions: QuestionResult[] = []

  // Build robustness (using score as baseline)
  const robustness: RobustnessResults = {
    conservative: {
      score: Math.round(backend.score.total_score * 0.85),
      grade: getGrade(backend.score.total_score * 0.85),
      context_budget: 3000,
      questions_answered: Math.round(backend.score.questions_answered * 0.8),
    },
    typical: {
      score: Math.round(backend.score.total_score),
      grade: backend.score.grade as Grade,
      context_budget: 6000,
      questions_answered: backend.score.questions_answered,
    },
    generous: {
      score: Math.round(Math.min(100, backend.score.total_score * 1.15)),
      grade: getGrade(Math.min(100, backend.score.total_score * 1.15)),
      context_budget: 12000,
      questions_answered: Math.round(Math.min(backend.score.total_questions, backend.score.questions_answered * 1.1)),
    },
  }

  // Build crawl info if available
  const crawl: CrawlInfo | undefined = backend.crawl ? {
    total_pages: backend.crawl.total_pages,
    total_words: backend.crawl.total_words,
    total_chunks: backend.crawl.total_chunks,
    urls_discovered: backend.crawl.urls_discovered,
    urls_failed: backend.crawl.urls_failed,
    max_depth_reached: backend.crawl.max_depth_reached,
    duration_seconds: backend.crawl.duration_seconds,
    pages: backend.crawl.pages.map(p => ({
      url: p.url,
      title: p.title,
      status_code: p.status_code,
      depth: p.depth,
      word_count: p.word_count,
      chunk_count: p.chunk_count,
    })),
  } : undefined

  return {
    run_id: backend.metadata.run_id,
    site_id: backend.metadata.site_id,
    domain: backend.metadata.domain,
    name: backend.metadata.company_name,
    url: `https://${backend.metadata.domain}`,
    score: backend.score.total_score,
    grade: backend.score.grade as Grade,
    created_at: backend.metadata.created_at,
    summary: {
      headline: `Your Findable Score is ${Math.round(backend.score.total_score ?? 0)}`,
      description: backend.score.grade_description ?? '',
      key_findings: [
        `${backend.score.questions_answered ?? 0} of ${backend.score.total_questions ?? 20} questions answered (${Math.round(backend.score.coverage_percentage ?? 0)}% coverage)`,
        `${backend.fixes?.critical_fixes ?? 0} critical fixes identified`,
        `${backend.fixes?.total_fixes ?? 0} total improvements available`,
      ],
    },
    categories,
    signals: {
      pages_crawled: backend.crawl?.total_pages ?? 0,
      chunks_created: backend.crawl?.total_chunks ?? 0,
      questions_answered: backend.score.questions_answered ?? 0,
      questions_total: backend.score.total_questions ?? 20,
      avg_retrieval_rank: 0,
    },
    fixes,
    questions,
    robustness,
    crawl,
  }
}

function getGrade(score: number): Grade {
  if (score >= 90) return 'A'
  if (score >= 80) return 'B'
  if (score >= 70) return 'C'
  if (score >= 60) return 'D'
  return 'F'
}

export interface ListRunsParams {
  page?: number
  per_page?: number  // Backend uses per_page
  status?: string
}

export const runsApi = {
  /**
   * List runs for a site
   * Backend: GET /v1/sites/{site_id}/runs
   */
  async list(siteId: string, params?: ListRunsParams): Promise<PaginatedResponse<Run>> {
    return apiClient.getPaginated<Run>(`/sites/${siteId}/runs`, params as Record<string, string | number | boolean | undefined>)
  },

  /**
   * Get a single run with progress
   * Backend: GET /v1/sites/{site_id}/runs/{run_id}
   */
  async get(siteId: string, runId: string): Promise<Run> {
    return apiClient.get<Run>(`/sites/${siteId}/runs/${runId}`)
  },

  /**
   * Start a new run for a site
   * Backend: POST /v1/sites/{site_id}/runs (returns 202 Accepted)
   */
  async create(siteId: string, data?: CreateRunRequest): Promise<Run> {
    return apiClient.post<Run>(`/sites/${siteId}/runs`, data)
  },

  /**
   * Cancel a running run
   * Backend: DELETE /v1/sites/{site_id}/runs/{run_id}
   */
  async cancel(siteId: string, runId: string): Promise<Run> {
    return apiClient.delete<Run>(`/sites/${siteId}/runs/${runId}`)
  },

  /**
   * Get the report for a completed run
   * Backend: GET /v1/reports/{report_id}
   * Transforms the nested backend format to flat frontend format
   */
  async getReport(reportId: string): Promise<Report> {
    console.log('Fetching report:', reportId)
    try {
      const backend = await apiClient.get<BackendReport>(`/reports/${reportId}`)
      console.log('Backend response keys:', Object.keys(backend || {}))
      console.log('Has metadata:', !!backend?.metadata)
      console.log('Has score:', !!backend?.score)

      if (!backend || !backend.metadata || !backend.score) {
        console.error('Invalid backend response:', backend)
        throw new Error('Invalid report data from server')
      }

      const report = transformReport(backend)
      console.log('Transformed report:', { name: report.name, score: report.score })
      return report
    } catch (error) {
      console.error('Failed to fetch/transform report:', error)
      throw error
    }
  },

  /**
   * Create an SSE connection for run progress
   * Backend: GET /v1/sites/{site_id}/runs/{run_id}/progress/stream
   *
   * Event types: progress, complete, failed, error
   */
  createProgressStream(siteId: string, runId: string): EventSource {
    return apiClient.createEventSource(`/sites/${siteId}/runs/${runId}/progress/stream`)
  },
}
