# Findable Frontend

Modern React/Next.js 14 SPA for the Findable Score Analyzer. Replaces the Jinja2 MVP templates with a full-featured dashboard.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui components
- **Data Fetching**: TanStack Query (React Query) v5
- **Client State**: Zustand with persistence
- **Forms**: React Hook Form + Zod validation
- **Charts**: Recharts for trend visualization
- **Testing**: Vitest + Playwright + MSW

## Features

### Authentication
- Login and registration pages
- JWT token persistence with localStorage
- Auth guard for protected routes
- Automatic token refresh handling

### Dashboard
- Stats overview (sites, average score, alerts, monitoring)
- Sites table with sorting and search
- Empty state for new users
- Quick actions (start run, delete site)

### Site Management
- Create new site with URL validation
- Site detail page with score ring
- Run history with status tracking
- Real-time SSE progress for active runs
- Score trend comparison between runs

### Site Settings
- Edit site name and URL
- Enable/disable monitoring
- Manage competitors
- Delete site with confirmation

### Reports
- Animated score ring visualization
- Category breakdown with progress bars
- Signal statistics grid
- Robustness analysis across context budgets
- "Show the math" expandable section
- Recommended fixes accordion
- Question results list

### Monitoring
- Score trend chart over time
- Snapshot history list
- Alerts with acknowledge action
- Enable/disable monitoring toggle

### Billing
- Plan comparison cards
- Current usage display
- Stripe checkout integration
- Billing portal access

### Polish
- Error boundary with retry
- Loading skeletons throughout
- Toast notifications
- Mobile responsive design
- 404 page
- E2E test suite

## Getting Started

```bash
# Install dependencies
npm install

# Create environment file
cp .env.local.example .env.local

# Start development server
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Run E2E tests
npx playwright install  # First time only
npm run e2e
```

## Project Structure

```
frontend/
├── app/                          # Next.js App Router
│   ├── (auth)/                   # Auth routes (login, register)
│   │   └── layout.tsx            # Centered auth layout
│   ├── (dashboard)/              # Authenticated routes
│   │   ├── layout.tsx            # Dashboard layout with nav
│   │   ├── dashboard/            # Main dashboard
│   │   ├── sites/
│   │   │   ├── new/              # New site form
│   │   │   └── [siteId]/         # Site detail
│   │   │       ├── settings/     # Site settings
│   │   │       └── monitoring/   # Monitoring & alerts
│   │   ├── reports/[reportId]/   # Full report view
│   │   └── billing/              # Plans and usage
│   ├── layout.tsx                # Root layout
│   ├── providers.tsx             # Client providers
│   └── not-found.tsx             # 404 page
├── components/
│   ├── ui/                       # Base UI components (button, input, card, etc.)
│   ├── layout/                   # Navbar, AuthGuard
│   ├── dashboard/                # StatCard, SitesTable
│   ├── site/                     # ActiveRunCard
│   ├── report/                   # TrendChart, ShowTheMath
│   └── shared/                   # GradeBadge, ScoreRing, skeletons, ErrorBoundary
├── lib/
│   ├── api/                      # API client modules
│   │   ├── client.ts             # Base HTTP client with auth
│   │   ├── auth.ts               # Auth endpoints
│   │   ├── sites.ts              # Sites CRUD
│   │   ├── runs.ts               # Runs & reports
│   │   ├── monitoring.ts         # Snapshots & alerts
│   │   └── billing.ts            # Plans & checkout
│   ├── hooks/                    # Custom hooks
│   │   ├── use-auth.ts           # Auth flow hook
│   │   ├── use-run-progress.ts   # SSE progress hook
│   │   └── use-toast.ts          # Toast notifications
│   ├── stores/                   # Zustand stores
│   │   ├── auth-store.ts         # User & token
│   │   └── preferences-store.ts  # UI preferences
│   └── utils/                    # Helper functions
├── types/                        # TypeScript interfaces
├── e2e/                          # Playwright E2E tests
│   ├── auth.spec.ts
│   ├── dashboard.spec.ts
│   ├── site.spec.ts
│   └── report.spec.ts
└── public/                       # Static assets
```

## Environment Variables

```bash
# Required
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional
NEXT_PUBLIC_APP_NAME=Findable Score
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## API Integration

All API calls use the typed client with automatic auth header injection:

```typescript
import { sitesApi, runsApi } from '@/lib/api'

// List sites with pagination
const { items, total } = await sitesApi.list({ page: 1, page_size: 20 })

// Create a site
const site = await sitesApi.create({ url: 'https://example.com', name: 'My Site' })

// Start a run
const run = await runsApi.create(siteId)

// Real-time progress via SSE
const { progress, isConnected, error } = useRunProgress(siteId, runId, {
  onComplete: () => console.log('Done!'),
})
```

## Design System

### Colors (Dark Theme)
- Background: slate-950 (#0a0f1a)
- Primary: teal-500 (#14b8a6)
- Accent: indigo-500 (#6366f1)

### Grade Colors
- A: cyan-400 (#22d3ee)
- B: green-400 (#4ade80)
- C: amber-400 (#fbbf24)
- D: orange-400 (#fb923c)
- F: red-400 (#f87171)

### Typography
- Headings: Instrument Serif
- Body: DM Sans
- Data/Mono: JetBrains Mono

## Testing

### Unit Tests (Vitest)
```bash
npm test              # Run all tests
npm test -- --watch   # Watch mode
npm test -- --coverage # With coverage
```

### E2E Tests (Playwright)
```bash
npx playwright install # Install browsers (first time)
npm run e2e           # Run all E2E tests
npm run e2e -- --ui   # Interactive UI mode
```

## Deployment

The frontend is designed to be deployed as a static site or with SSR:

```bash
# Build
npm run build

# Start production server
npm start

# Or export static (if all routes are static)
npm run build && npx next export
```

## Contributing

1. Follow the existing code style
2. Add tests for new features
3. Run `npm run lint` before committing
4. Use conventional commit messages
