'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2, Trash2, Bell, BellOff } from 'lucide-react'
import { sitesApi, ApiClientError } from '@/lib/api'
import { toast } from '@/lib/hooks'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/shared'

interface SettingsPageProps {
  params: { siteId: string }
}

const updateSiteSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
})

type UpdateSiteForm = z.infer<typeof updateSiteSchema>

export default function SiteSettingsPage({ params }: SettingsPageProps) {
  const { siteId } = params
  const router = useRouter()
  const queryClient = useQueryClient()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const { data: site, isLoading } = useQuery({
    queryKey: ['sites', siteId],
    queryFn: () => sitesApi.get(siteId),
  })

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<UpdateSiteForm>({
    resolver: zodResolver(updateSiteSchema),
    values: site ? { name: site.name || '' } : undefined,
  })

  const updateMutation = useMutation({
    mutationFn: (data: Partial<UpdateSiteForm>) => sitesApi.update(siteId, data),
    onSuccess: () => {
      toast({ title: 'Settings saved' })
      queryClient.invalidateQueries({ queryKey: ['sites', siteId] })
      queryClient.invalidateQueries({ queryKey: ['sites'] })
    },
    onError: (err) => {
      toast({
        title: 'Failed to save settings',
        description: err instanceof ApiClientError ? err.message : 'Please try again.',
        variant: 'destructive',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => sitesApi.delete(siteId),
    onSuccess: () => {
      toast({ title: 'Site deleted' })
      queryClient.invalidateQueries({ queryKey: ['sites'] })
      router.push('/dashboard')
    },
    onError: () => {
      toast({
        title: 'Failed to delete site',
        description: 'Please try again.',
        variant: 'destructive',
      })
    },
  })

  const monitoringMutation = useMutation({
    mutationFn: (enable: boolean) =>
      enable ? sitesApi.enableMonitoring(siteId) : sitesApi.disableMonitoring(siteId),
    onSuccess: (_, enable) => {
      toast({ title: enable ? 'Monitoring enabled' : 'Monitoring disabled' })
      queryClient.invalidateQueries({ queryKey: ['sites', siteId] })
    },
    onError: () => {
      toast({
        title: 'Failed to update monitoring',
        description: 'Please try again.',
        variant: 'destructive',
      })
    },
  })

  const onSubmit = (data: UpdateSiteForm) => {
    updateMutation.mutate(data)
  }

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="p-6 space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-32" />
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!site) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-medium mb-2">Site not found</h2>
        <Link href="/dashboard">
          <Button>Back to Dashboard</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Back link */}
      <Link
        href={`/sites/${siteId}`}
        className="inline-flex items-center gap-2 text-sm text-foreground-muted hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Site
      </Link>

      <h1 className="font-serif text-3xl font-medium">Site Settings</h1>

      {/* General settings */}
      <Card>
        <CardHeader>
          <CardTitle>General</CardTitle>
          <CardDescription>Basic information about your site</CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="domain">Domain</Label>
              <Input id="domain" value={site.domain} disabled className="bg-background-secondary/50" />
              <p className="text-xs text-foreground-muted">Domain cannot be changed after creation.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Site Name</Label>
              <Input id="name" {...register('name')} />
              {errors.name && (
                <p className="text-sm text-red-400">{errors.name.message}</p>
              )}
            </div>
            <Button type="submit" disabled={!isDirty || updateMutation.isPending}>
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </CardContent>
        </form>
      </Card>

      {/* Monitoring */}
      <Card>
        <CardHeader>
          <CardTitle>Monitoring</CardTitle>
          <CardDescription>Automatic daily score tracking</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">
                {site.monitoring_enabled ? 'Monitoring Active' : 'Monitoring Disabled'}
              </p>
              <p className="text-sm text-foreground-muted">
                {site.monitoring_enabled
                  ? 'Your site is being checked daily for findability changes.'
                  : 'Enable to receive alerts when your score changes.'}
              </p>
            </div>
            <Button
              variant={site.monitoring_enabled ? 'outline' : 'default'}
              onClick={() => monitoringMutation.mutate(!site.monitoring_enabled)}
              disabled={monitoringMutation.isPending}
            >
              {monitoringMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : site.monitoring_enabled ? (
                <>
                  <BellOff className="h-4 w-4 mr-2" />
                  Disable
                </>
              ) : (
                <>
                  <Bell className="h-4 w-4 mr-2" />
                  Enable
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Competitors info */}
      <Card>
        <CardHeader>
          <CardTitle>Competitors</CardTitle>
          <CardDescription>Track how you compare to competing sites</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-foreground-muted">
            {site.competitor_count > 0
              ? `${site.competitor_count} competitor${site.competitor_count !== 1 ? 's' : ''} configured.`
              : 'No competitors configured yet.'}
          </p>
          <p className="text-xs text-foreground-muted mt-2">
            Competitor management coming soon.
          </p>
        </CardContent>
      </Card>

      {/* Danger zone */}
      <Card className="border-red-500/30">
        <CardHeader>
          <CardTitle className="text-red-400">Danger Zone</CardTitle>
          <CardDescription>Irreversible actions</CardDescription>
        </CardHeader>
        <CardContent>
          {showDeleteConfirm ? (
            <div className="space-y-4">
              <p className="text-sm text-foreground-muted">
                Are you sure you want to delete <strong>{site.name || site.domain}</strong>? This will permanently
                remove all runs, reports, and monitoring data. This action cannot be undone.
              </p>
              <div className="flex gap-2">
                <Button
                  variant="destructive"
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Deleting...
                    </>
                  ) : (
                    'Yes, Delete Site'
                  )}
                </Button>
                <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Delete Site</p>
                <p className="text-sm text-foreground-muted">
                  Permanently delete this site and all its data.
                </p>
              </div>
              <Button variant="outline" onClick={() => setShowDeleteConfirm(true)}>
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
