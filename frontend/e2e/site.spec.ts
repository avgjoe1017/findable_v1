import { test, expect } from '@playwright/test'

test.describe('Site Management', () => {
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

  test('should display new site form', async ({ page }) => {
    await page.goto('/sites/new')

    await expect(page.getByLabel('Website URL')).toBeVisible()
    await expect(page.getByLabel('Site Name')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Add Site' })).toBeVisible()
  })

  test('should show validation error for invalid URL', async ({ page }) => {
    await page.goto('/sites/new')

    await page.getByLabel('Website URL').fill('not-a-url')
    await page.getByLabel('Site Name').fill('Test Site')
    await page.getByRole('button', { name: 'Add Site' }).click()

    await expect(page.getByText('Please enter a valid URL')).toBeVisible()
  })

  test('should auto-generate name from URL', async ({ page }) => {
    await page.goto('/sites/new')

    await page.getByLabel('Website URL').fill('https://example.com')
    await page.getByLabel('Website URL').blur()

    await expect(page.getByLabel('Site Name')).toHaveValue('example.com')
  })

  test('should display site detail page', async ({ page }) => {
    const mockSite = {
      id: 'site-1',
      user_id: '1',
      domain: 'example.com',
      name: 'Example Site',
      business_model: 'unknown',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      latest_score: 75,
      latest_grade: 'B',
      latest_run_id: 'run-1',
      monitoring_enabled: true,
      competitor_count: 0,
    }

    await page.route('**/v1/sites/site-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockSite }),
      })
    })

    await page.route('**/v1/sites/site-1/runs*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [],
          meta: {
            total: 0,
            page: 1,
            per_page: 10,
            total_pages: 0,
            has_next: false,
            has_prev: false,
          },
        }),
      })
    })

    await page.goto('/sites/site-1')

    await expect(page.getByRole('heading', { name: 'Example Site' })).toBeVisible()
    await expect(page.getByText('75')).toBeVisible()
    await expect(page.getByRole('button', { name: 'New Run' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible()
  })

  test('should display site settings page', async ({ page }) => {
    const mockSite = {
      id: 'site-1',
      user_id: '1',
      domain: 'example.com',
      name: 'Example Site',
      business_model: 'unknown',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      latest_score: 75,
      latest_grade: 'B',
      latest_run_id: 'run-1',
      monitoring_enabled: false,
      competitor_count: 0,
    }

    await page.route('**/v1/sites/site-1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockSite }),
      })
    })

    await page.goto('/sites/site-1/settings')

    await expect(page.getByRole('heading', { name: 'Site Settings' })).toBeVisible()
    await expect(page.getByLabel('Site Name')).toHaveValue('Example Site')
    await expect(page.getByLabel('Domain')).toHaveValue('example.com')
    await expect(page.getByRole('heading', { name: 'Monitoring' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Competitors' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Danger Zone' })).toBeVisible()
  })
})
