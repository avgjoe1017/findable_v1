import type { Metadata } from 'next'
import { Providers } from './providers'
import './globals.css'

export const metadata: Metadata = {
  title: 'Findable Score - AI Answer Engine Visibility',
  description: 'Measure whether AI answer engines can retrieve and use your website as a source.',
  keywords: ['AI', 'SEO', 'findability', 'answer engines', 'visibility'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background antialiased">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}
