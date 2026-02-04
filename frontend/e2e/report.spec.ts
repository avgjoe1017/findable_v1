import { test, expect } from '@playwright/test'

test.describe('Report', () => {
  test.beforeEach(async ({ page }) => {
    // Set up mock auth
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'mock-token')
      localStorage.setItem('auth-storage', JSON.stringify({
        state: {
          user: {
            id: '1',
            email: 'test@example.com',
            name: 'Test User',
            plan: 'starter',
          },
          token: 'mock-token',
          isHydrated: true,
        },
        version: 0,
      }))
    })
  })

  const mockReport = {
    run_id: 'report-1',
    site_id: 'site-1',
    url: 'https://example.com',
    name: 'Example Site',
    score: 75,
    grade: 'B',
    created_at: new Date().toISOString(),
    summary: {
      headline: 'Good findability with room for improvement',
      description: 'Your site performs well but has areas that could be optimized.',
      key_findings: [
        'Strong coverage of core topics',
        'Some pages lack structured data',
      ],
    },
    categories: [
      { name: 'Coverage', slug: 'coverage', score: 0.8, weight: 0.3, description: 'How well questions are answered' },
      { name: 'Extractability', slug: 'extractability', score: 0.7, weight: 0.25, description: 'Ease of content extraction' },
      { name: 'Citability', slug: 'citability', score: 0.75, weight: 0.2, description: 'Quotable content quality' },
      { name: 'Trust', slug: 'trust', score: 0.8, weight: 0.15, description: 'Entity legitimacy' },
      { name: 'Conflicts', slug: 'conflicts', score: 0.9, weight: 0.05, description: 'Contradicting information' },
      { name: 'Redundancy', slug: 'redundancy', score: 0.85, weight: 0.05, description: 'Boilerplate presence' },
    ],
    signals: {
      pages_crawled: 50,
      chunks_created: 200,
      questions_answered: 18,
      questions_total: 25,
      avg_retrieval_rank: 2.5,
    },
    fixes: [
      {
        id: 'fix-1',
        category: 'Schema',
        severity: 'high',
        title: 'Add FAQ Schema to FAQ pages',
        description: 'Your FAQ pages lack structured data markup.',
        impact_estimate: 5,
        implementation: 'Add FAQPage schema to your FAQ sections.',
        affected_questions: ['q1', 'q2'],
      },
    ],
    questions: [
      { question: 'What services do you offer?', question_type: 'universal', answered: true, retrieval_rank: 1, chunk_used: 'chunk-1', confidence: 0.95 },
      { question: 'What is your pricing?', question_type: 'universal', answered: false, retrieval_rank: null, chunk_used: null, confidence: null },
    ],
    robustness: {
      conservative: { score: 70, grade: 'C', context_budget: 3000, questions_answered: 15 },
      typical: { score: 75, grade: 'B', context_budget: 6000, questions_answered: 18 },
      generous: { score: 80, grade: 'B', context_budget: 12000, questions_answered: 20 },
    },
  }

  test('should display report with score ring', async ({ page }) => {
    await page.route('**/v1/reports/report-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: mockReport }),
      })
    })

    await page.goto('/reports/report-1')

    await expect(page.getByRole('heading', { name: 'Example Site' })).toBeVisible()
    await expect(page.getByText('75')).toBeVisible()
    await expect(page.getByText('B').first()).toBeVisible()
    await expect(page.getByText('Good findability with room for improvement')).toBeVisible()
  })

  test('should display signal stats', async ({ page }) => {
    await page.route('**/v1/reports/report-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: mockReport }),
      })
    })

    await page.goto('/reports/report-1')

    await expect(page.getByText('Pages Crawled')).toBeVisible()
    await expect(page.getByText('50')).toBeVisible()
    await expect(page.getByText('Chunks Created')).toBeVisible()
    await expect(page.getByText('200')).toBeVisible()
    await expect(page.getByText('Questions Answered')).toBeVisible()
    await expect(page.getByText('18/25')).toBeVisible()
  })

  test('should display category breakdown', async ({ page }) => {
    await page.route('**/v1/reports/report-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: mockReport }),
      })
    })

    await page.goto('/reports/report-1')

    await expect(page.getByText('Score Breakdown')).toBeVisible()
    await expect(page.getByText('Coverage')).toBeVisible()
    await expect(page.getByText('Extractability')).toBeVisible()
    await expect(page.getByText('Citability')).toBeVisible()
  })

  test('should display robustness analysis', async ({ page }) => {
    await page.route('**/v1/reports/report-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: mockReport }),
      })
    })

    await page.goto('/reports/report-1')

    await expect(page.getByText('Robustness Analysis')).toBeVisible()
    await expect(page.getByText('Conservative')).toBeVisible()
    await expect(page.getByText('Typical')).toBeVisible()
    await expect(page.getByText('Generous')).toBeVisible()
  })

  test('should toggle show the math section', async ({ page }) => {
    await page.route('**/v1/reports/report-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: mockReport }),
      })
    })

    await page.goto('/reports/report-1')

    // Find and click the "Show" button
    await page.getByRole('button', { name: 'Show' }).click()

    await expect(page.getByText('Score Formula')).toBeVisible()
    await expect(page.getByText('Category Contributions')).toBeVisible()

    // Click "Hide" to collapse
    await page.getByRole('button', { name: 'Hide' }).click()
    await expect(page.getByText('Score Formula')).not.toBeVisible()
  })

  test('should expand fix accordion', async ({ page }) => {
    await page.route('**/v1/reports/report-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: mockReport }),
      })
    })

    await page.goto('/reports/report-1')

    await expect(page.getByText('Recommended Fixes')).toBeVisible()
    await expect(page.getByText('Add FAQ Schema to FAQ pages')).toBeVisible()

    // Click to expand
    await page.getByText('Add FAQ Schema to FAQ pages').click()

    await expect(page.getByText('Your FAQ pages lack structured data markup.')).toBeVisible()
    await expect(page.getByText('Add FAQPage schema to your FAQ sections.')).toBeVisible()
  })
})
