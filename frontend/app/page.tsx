import { redirect } from 'next/navigation'

export default function Home() {
  // Root redirects to dashboard (auth is handled by AuthGuard)
  redirect('/dashboard')
}
