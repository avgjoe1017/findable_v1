'use client'

import { useQuery, useMutation } from '@tanstack/react-query'
import { Check, Zap } from 'lucide-react'
import { billingApi } from '@/lib/api'
import { toast } from '@/lib/hooks'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/shared'
import { useAuthStore, selectUser } from '@/lib/stores'
import type { Plan, PlanTier } from '@/types'

export default function BillingPage() {
  const user = useAuthStore(selectUser)

  const { data: plans, isLoading: isLoadingPlans } = useQuery({
    queryKey: ['billing', 'plans'],
    queryFn: () => billingApi.getPlans(),
  })

  const { data: usage, isLoading: isLoadingUsage } = useQuery({
    queryKey: ['billing', 'usage'],
    queryFn: () => billingApi.getUsage(),
  })

  const checkoutMutation = useMutation({
    mutationFn: ({ tier, interval }: { tier: PlanTier; interval: 'monthly' | 'yearly' }) =>
      billingApi.createCheckout(tier, interval),
    onSuccess: (data) => {
      window.location.href = data.url
    },
    onError: () => {
      toast({
        title: 'Failed to create checkout',
        description: 'Please try again.',
        variant: 'destructive',
      })
    },
  })

  const portalMutation = useMutation({
    mutationFn: () => billingApi.createPortal(),
    onSuccess: (data) => {
      window.location.href = data.url
    },
    onError: () => {
      toast({
        title: 'Failed to open billing portal',
        description: 'Please try again.',
        variant: 'destructive',
      })
    },
  })

  if (isLoadingPlans || isLoadingUsage) {
    return (
      <div className="space-y-8">
        <div>
          <Skeleton className="h-8 w-32 mb-2" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-40 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  const currentPlan = user?.plan || 'starter'

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-serif text-3xl font-medium">Billing</h1>
        <p className="text-foreground-muted mt-1">
          Manage your subscription and view usage
        </p>
      </div>

      {/* Current usage */}
      {usage && (
        <Card>
          <CardHeader>
            <CardTitle>Current Usage</CardTitle>
            <CardDescription>
              Your usage for the current billing period
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-foreground-muted">Sites</span>
                  <span className="font-mono">{usage.sites_used} / {usage.sites_limit}</span>
                </div>
                <Progress value={(usage.sites_used / usage.sites_limit) * 100} />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-foreground-muted">Runs this month</span>
                  <span className="font-mono">{usage.runs_used} / {usage.runs_limit}</span>
                </div>
                <Progress value={(usage.runs_used / usage.runs_limit) * 100} />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Plans */}
      <div>
        <h2 className="font-serif text-xl font-medium mb-4">Plans</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans?.map((plan) => (
            <PlanCard
              key={plan.tier}
              plan={plan}
              isCurrent={currentPlan === plan.tier}
              onSelect={(interval) => checkoutMutation.mutate({ tier: plan.tier, interval })}
              isLoading={checkoutMutation.isPending}
            />
          ))}
        </div>
      </div>

      {/* Manage subscription */}
      {currentPlan !== 'starter' && (
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Manage Subscription</p>
                <p className="text-sm text-foreground-muted">
                  Update payment method, view invoices, or cancel your subscription
                </p>
              </div>
              <Button
                variant="outline"
                onClick={() => portalMutation.mutate()}
                disabled={portalMutation.isPending}
              >
                Open Billing Portal
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

interface PlanCardProps {
  plan: Plan
  isCurrent: boolean
  onSelect: (interval: 'monthly' | 'yearly') => void
  isLoading: boolean
}

function PlanCard({ plan, isCurrent, onSelect, isLoading }: PlanCardProps) {
  const isPopular = plan.tier === 'professional'

  return (
    <Card className={cn(
      'relative',
      isPopular && 'border-primary ring-1 ring-primary',
      isCurrent && 'border-green-500/50'
    )}>
      {isPopular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-primary text-primary-foreground text-xs font-medium rounded-full">
          Most Popular
        </div>
      )}
      {isCurrent && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-green-500 text-white text-xs font-medium rounded-full">
          Current Plan
        </div>
      )}
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {plan.tier === 'agency' && <Zap className="h-5 w-5 text-amber-400" />}
          {plan.name}
        </CardTitle>
        <CardDescription>
          <span className="text-3xl font-bold text-foreground">${plan.price_monthly}</span>
          <span className="text-foreground-muted">/month</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <ul className="space-y-2">
          {plan.features.map((feature, i) => (
            <li key={i} className="flex items-start gap-2 text-sm">
              <Check className={cn(
                'h-4 w-4 mt-0.5',
                feature.included ? 'text-green-400' : 'text-foreground-muted opacity-50'
              )} />
              <span className={cn(!feature.included && 'text-foreground-muted line-through')}>
                {feature.name}
              </span>
            </li>
          ))}
        </ul>

        <div className="text-xs text-foreground-muted space-y-1">
          <p>• {plan.limits.sites} sites</p>
          <p>• {plan.limits.competitors_per_site} competitors per site</p>
          <p>• {plan.limits.runs_per_month} runs per month</p>
          <p>• {plan.limits.custom_questions} custom questions</p>
        </div>

        {!isCurrent && plan.price_monthly > 0 ? (
          <div className="space-y-2">
            <Button
              className="w-full"
              onClick={() => onSelect('monthly')}
              disabled={isLoading}
            >
              Subscribe Monthly
            </Button>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => onSelect('yearly')}
              disabled={isLoading}
            >
              Subscribe Yearly (Save 20%)
            </Button>
          </div>
        ) : !isCurrent ? (
          <Button className="w-full" disabled>
            Free Forever
          </Button>
        ) : (
          <Button className="w-full" variant="outline" disabled>
            Current Plan
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
