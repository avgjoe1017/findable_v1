import { test, expect } from '@playwright/test'

test.describe('Dashboard', () => {
  // Mock authenticated state
  test.beforeEach(async ({ page }) => {
    // Set up mock auth token
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

  test('should display dashboard with stats cards', async ({ page }) => {
    await page.route('**/v1/sites*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [],
          meta: {
            total: 0,
            page: 1,
            per_page: 50,
            total_pages: 0,
            has_next: false,
            has_prev: false,
          },
        }),
      })
    })

    await page.goto('/dashboard')

    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
    await expect(page.getByText('Total Sites')).toBeVisible()
    await expect(page.getByText('Average Score')).toBeVisible()
    await expect(page.getByText('Needs Attention')).toBeVisible()
    await expect(page.getByText('Monitoring Active')).toBeVisible()
  })

  test('should show empty state when no sites exist', async ({ page }) => {
    await page.route('**/v1/sites*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [],
          meta: {
            total: 0,
            page: 1,
            per_page: 50,
            total_pages: 0,
            has_next: false,
            has_prev: false,
          },
        }),
      })
    })

    await page.goto('/dashboard')

    await expect(page.getByText('No sites yet')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Add Your First Site' })).toBeVisible()
  })

  test('should display sites in table', async ({ page }) => {
    await page.route('**/v1/sites*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [
            {
              id: '1',
              user_id: '1',
              domain: 'example.com',
              name: 'Example Site',
              business_model: 'unknown',
              created_at: new Date().toISOString(),
              latest_score: 75,
              latest_grade: 'B',
              latest_run_id: 'run-1',
              monitoring_enabled: true,
              competitor_count: 0,
            },
          ],
          meta: {
            total: 1,
            page: 1,
            per_page: 50,
            total_pages: 1,
            has_next: false,
            has_prev: false,
          },
        }),
      })
    })

    await page.goto('/dashboard')

    await expect(page.getByText('Example Site')).toBeVisible()
    await expect(page.getByText('75')).toBeVisible()
    await expect(page.getByText('B')).toBeVisible()
    await expect(page.getByText('Active')).toBeVisible()
  })

  test('should navigate to new site page', async ({ page }) => {
    await page.route('**/v1/sites*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [],
          meta: {
            total: 0,
            page: 1,
            per_page: 50,
            total_pages: 0,
            has_next: false,
            has_prev: false,
          },
        }),
      })
    })

    await page.goto('/dashboard')
    await page.getByRole('link', { name: 'Add Your First Site' }).click()

    await expect(page).toHaveURL('/sites/new')
    await expect(page.getByRole('heading', { name: 'Add a New Site' })).toBeVisible()
  })
})
