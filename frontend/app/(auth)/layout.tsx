export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-md space-y-8">
        {/* Logo */}
        <div className="text-center">
          <h1 className="font-serif text-4xl font-medium text-primary">
            Findable
          </h1>
          <p className="mt-2 text-sm text-foreground-muted">
            AI Answer Engine Visibility
          </p>
        </div>

        {children}
      </div>
    </div>
  )
}
