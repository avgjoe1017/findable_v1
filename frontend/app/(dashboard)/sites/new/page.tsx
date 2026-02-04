'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { sitesApi, ApiClientError } from '@/lib/api'
import { toast } from '@/lib/hooks'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const createSiteSchema = z.object({
  domain: z.string()
    .min(1, 'Please enter a domain or URL')
    .refine(val => {
      // Allow full URLs or just domain names
      try {
        if (val.includes('://')) {
          new URL(val)
        }
        return true
      } catch {
        return false
      }
    }, {
      message: 'Please enter a valid domain or URL',
    }),
  name: z.string().max(100, 'Name must be less than 100 characters').optional(),
})

type CreateSiteForm = z.infer<typeof createSiteSchema>

export default function NewSitePage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
  } = useForm<CreateSiteForm>({
    resolver: zodResolver(createSiteSchema),
    defaultValues: {
      domain: '',
      name: '',
    },
  })

  const createSiteMutation = useMutation({
    mutationFn: (data: CreateSiteForm) => sitesApi.create({
      domain: data.domain,
      name: data.name || undefined,
    }),
    onSuccess: (site) => {
      toast({
        title: 'Site created',
        description: 'Your site has been added. Starting initial audit...',
      })
      queryClient.invalidateQueries({ queryKey: ['sites'] })
      router.push(`/sites/${site.id}`)
    },
    onError: (err) => {
      if (err instanceof ApiClientError) {
        setError(err.message)
      } else {
        setError('An unexpected error occurred')
      }
    },
  })

  const onSubmit = (data: CreateSiteForm) => {
    setError(null)
    createSiteMutation.mutate(data)
  }

  // Auto-generate name from domain/URL
  const domain = watch('domain')
  const handleDomainBlur = () => {
    if (domain && !watch('name')) {
      try {
        let hostname = domain
        if (domain.includes('://')) {
          const urlObj = new URL(domain)
          hostname = urlObj.hostname
        }
        hostname = hostname.replace(/^www\./, '')
        setValue('name', hostname)
      } catch {
        // Invalid URL, ignore
      }
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Back link */}
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-2 text-sm text-foreground-muted hover:text-foreground mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </Link>

      <Card>
        <CardHeader>
          <CardTitle className="font-serif text-2xl">Add a New Site</CardTitle>
          <CardDescription>
            Enter your website URL to start measuring its AI findability score.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-6">
            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="domain">Website URL</Label>
              <Input
                id="domain"
                type="text"
                placeholder="https://example.com"
                {...register('domain')}
                onBlur={handleDomainBlur}
              />
              {errors.domain && (
                <p className="text-sm text-red-400">{errors.domain.message}</p>
              )}
              <p className="text-xs text-foreground-muted">
                We'll crawl your site to analyze its content for AI findability.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">Site Name</Label>
              <Input
                id="name"
                type="text"
                placeholder="My Website"
                {...register('name')}
              />
              {errors.name && (
                <p className="text-sm text-red-400">{errors.name.message}</p>
              )}
              <p className="text-xs text-foreground-muted">
                A friendly name to identify this site in your dashboard (optional).
              </p>
            </div>

            <div className="flex gap-4 pt-4">
              <Button type="submit" disabled={createSiteMutation.isPending}>
                {createSiteMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  'Add Site'
                )}
              </Button>
              <Button type="button" variant="outline" onClick={() => router.back()}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </form>
      </Card>

      {/* Info section */}
      <div className="mt-8 p-6 rounded-xl bg-card/50 border border-border/30">
        <h3 className="font-medium mb-2">What happens next?</h3>
        <ul className="space-y-2 text-sm text-foreground-muted">
          <li className="flex items-start gap-2">
            <span className="text-primary">1.</span>
            We'll crawl your site and extract relevant content
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary">2.</span>
            Generate questions that AI engines might ask about your business
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary">3.</span>
            Simulate how well AI can find and cite your content
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary">4.</span>
            Provide actionable fixes to improve your findability
          </li>
        </ul>
      </div>
    </div>
  )
}
