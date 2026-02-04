'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, Settings, CreditCard, LogOut, Bell } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/hooks'
import { useAuthStore, selectUser } from '@/lib/stores'

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/billing', label: 'Billing', icon: CreditCard },
]

export function Navbar() {
  const pathname = usePathname()
  const { logout, isLoggingOut } = useAuth()
  const user = useAuthStore(selectUser)

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 max-w-screen-2xl items-center px-4">
        {/* Logo */}
        <Link href="/dashboard" className="mr-6 flex items-center space-x-2">
          <span className="font-serif text-xl font-medium text-primary">
            Findable
          </span>
        </Link>

        {/* Nav links */}
        <nav className="flex items-center gap-1 text-sm">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-foreground-muted hover:bg-card-hover hover:text-foreground'
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            )
          })}
        </nav>

        {/* Right side */}
        <div className="ml-auto flex items-center gap-2">
          {/* Notifications */}
          <Button variant="ghost" size="icon" className="relative">
            <Bell className="h-4 w-4" />
            {/* Notification dot */}
            {/* <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-red-500" /> */}
          </Button>

          {/* User menu */}
          <div className="flex items-center gap-2 pl-2 border-l border-border/40">
            <div className="hidden sm:block text-right">
              <p className="text-sm font-medium">{user?.name || user?.email}</p>
              <p className="text-xs text-foreground-muted capitalize">{user?.plan || 'starter'} plan</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={logout}
              disabled={isLoggingOut}
              className="text-foreground-muted hover:text-foreground"
            >
              <LogOut className="h-4 w-4" />
              <span className="sr-only">Sign out</span>
            </Button>
          </div>
        </div>
      </div>
    </header>
  )
}
