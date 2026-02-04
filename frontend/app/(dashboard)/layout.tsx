import { Navbar } from '@/components/layout/navbar'
import { AuthGuard } from '@/components/layout/auth-guard'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <AuthGuard>
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 container max-w-screen-2xl px-4 py-8">
          {children}
        </main>
      </div>
    </AuthGuard>
  )
}
