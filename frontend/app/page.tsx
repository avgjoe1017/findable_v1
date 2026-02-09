'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore, selectIsAuthenticated, selectIsHydrated } from '@/lib/stores'
import LandingPage from '@/components/marketing/landing-page'

export default function Home() {
  const router = useRouter()
  const isAuthenticated = useAuthStore(selectIsAuthenticated)
  const isHydrated = useAuthStore(selectIsHydrated)

  useEffect(() => {
    if (isHydrated && isAuthenticated) {
      router.replace('/dashboard')
    }
  }, [isHydrated, isAuthenticated, router])

  // Dark background while hydrating to prevent flash
  if (!isHydrated) {
    return <div className="min-h-screen bg-background" />
  }

  // Redirect in progress
  if (isAuthenticated) {
    return <div className="min-h-screen bg-background" />
  }

  return <LandingPage />
}
