'use client'

import { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useAuthStore, selectIsAuthenticated, selectIsHydrated } from '@/lib/stores'
import { Skeleton } from '@/components/shared'

interface AuthGuardProps {
  children: React.ReactNode
}

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter()
  const pathname = usePathname()
  const isAuthenticated = useAuthStore(selectIsAuthenticated)
  const isHydrated = useAuthStore(selectIsHydrated)

  useEffect(() => {
    if (isHydrated && !isAuthenticated) {
      // Redirect to login, preserving the intended destination
      const returnUrl = encodeURIComponent(pathname)
      router.replace(`/login?returnUrl=${returnUrl}`)
    }
  }, [isHydrated, isAuthenticated, pathname, router])

  // Show loading state while hydrating
  if (!isHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="space-y-4 w-full max-w-md p-8">
          <Skeleton className="h-8 w-32 mx-auto" />
          <Skeleton className="h-4 w-48 mx-auto" />
          <div className="space-y-2 pt-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        </div>
      </div>
    )
  }

  // Show nothing while redirecting
  if (!isAuthenticated) {
    return null
  }

  return <>{children}</>
}
