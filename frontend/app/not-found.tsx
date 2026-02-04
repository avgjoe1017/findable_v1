import Link from 'next/link'
import { Home, ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="text-center max-w-md">
        {/* 404 display */}
        <div className="mb-8">
          <h1 className="font-mono text-8xl font-bold text-primary">404</h1>
          <div className="h-1 w-24 mx-auto mt-4 bg-gradient-to-r from-transparent via-primary to-transparent" />
        </div>

        {/* Message */}
        <h2 className="font-serif text-2xl font-medium mb-2">Page not found</h2>
        <p className="text-foreground-muted mb-8">
          The page you're looking for doesn't exist or has been moved.
        </p>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Button asChild>
            <Link href="/dashboard">
              <Home className="h-4 w-4 mr-2" />
              Go to Dashboard
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="javascript:history.back()">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Go Back
            </Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
