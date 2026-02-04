// User types
export interface User {
  id: string
  email: string
  name: string | null
  plan: PlanTier  // Backend returns 'plan', not 'plan_tier'
  is_active: boolean
  is_verified: boolean
  created_at: string
  updated_at: string
}

export type PlanTier = 'starter' | 'professional' | 'agency'

// Site types
export interface Site {
  id: string
  user_id: string
  domain: string
  name: string | null
  business_model: string
  created_at: string
  updated_at: string
  latest_score: number | null
  latest_grade: Grade | null
  latest_run_id: string | null
  monitoring_enabled: boolean
  competitor_count: number
}

export interface SiteWithRuns extends Site {
  runs: Run[]
}

export type Grade = 'A' | 'B' | 'C' | 'D' | 'F'

// Run types
export interface Run {
  id: string
  site_id: string
  status: RunStatus
  score: number | null
  grade: Grade | null
  report_id: string | null
  created_at: string
  completed_at: string | null
  error_message: string | null
}

export type RunStatus = 'queued' | 'pending' | 'crawling' | 'extracting' | 'chunking' | 'embedding' | 'simulating' | 'scoring' | 'generating_questions' | 'generating_fixes' | 'assembling' | 'complete' | 'failed'

export interface RunProgress {
  status: RunStatus
  progress: number
  message: string
  current_step?: string
  pages_crawled?: number
  pages_total?: number
}

// Report types
export interface Report {
  run_id: string
  site_id: string
  domain: string
  name: string
  url: string
  score: number
  grade: Grade
  created_at: string
  summary: ReportSummary
  categories: CategoryScore[]
  signals: SignalStats
  fixes: Fix[]
  questions: QuestionResult[]
  robustness: RobustnessResults
  crawl?: CrawlInfo
}

export interface ReportSummary {
  headline: string
  description: string
  key_findings: string[]
}

export interface CategoryScore {
  name: string
  slug: string
  score: number
  weight: number
  description: string
}

export interface SignalStats {
  pages_crawled: number
  chunks_created: number
  questions_answered: number
  questions_total: number
  avg_retrieval_rank: number
}

export interface CrawledPage {
  url: string
  title: string | null
  status_code: number
  depth: number
  word_count: number
  chunk_count: number
}

export interface CrawlInfo {
  total_pages: number
  total_words: number
  total_chunks: number
  urls_discovered: number
  urls_failed: number
  max_depth_reached: number
  duration_seconds: number
  pages: CrawledPage[]
}

export interface Fix {
  id: string
  category: string
  severity: FixSeverity
  title: string
  description: string
  impact_estimate: number
  implementation: string
  affected_questions: string[]
}

export type FixSeverity = 'critical' | 'high' | 'medium' | 'low'

export interface QuestionResult {
  question: string
  question_type: 'universal' | 'derived' | 'custom'
  answered: boolean
  retrieval_rank: number | null
  chunk_used: string | null
  confidence: number | null
}

export interface RobustnessResults {
  conservative: BandResult
  typical: BandResult
  generous: BandResult
}

export interface BandResult {
  score: number
  grade: Grade
  context_budget: number
  questions_answered: number
}

// Monitoring types
export interface Snapshot {
  id: string
  site_id: string
  score: number
  grade: Grade
  created_at: string
}

export interface Alert {
  id: string
  site_id: string
  type: AlertType
  message: string
  severity: AlertSeverity
  created_at: string
  acknowledged: boolean
}

export type AlertType = 'score_drop' | 'competitor_overtake' | 'observation_divergence'
export type AlertSeverity = 'info' | 'warning' | 'critical'

// Billing types
export interface Plan {
  tier: PlanTier
  name: string
  price_monthly: number
  price_yearly: number
  features: PlanFeature[]
  limits: PlanLimits
}

export interface PlanFeature {
  name: string
  included: boolean
  description?: string
}

export interface PlanLimits {
  sites: number
  competitors_per_site: number
  runs_per_month: number
  custom_questions: number
  monitoring: boolean
  api_access: boolean
}

export interface Usage {
  runs_used: number
  runs_limit: number
  sites_used: number
  sites_limit: number
  period_start: string
  period_end: string
}

// API types (matches backend { data: T, meta?: {} } format)
export interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

export interface ApiError {
  error?: {
    code: string
    message: string
    field?: string
    details?: Record<string, unknown>
  }
  // FastAPI-Users format (for auth errors)
  detail?: string | { msg: string; type: string }[]
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Auth types
export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  name?: string
}

export interface AuthResponse {
  user: User
  access_token: string
  token_type: string
}

// Form types
export interface CreateSiteRequest {
  domain: string
  name?: string
}

export interface CreateRunRequest {
  custom_questions?: string[]
  force_recrawl?: boolean
}
