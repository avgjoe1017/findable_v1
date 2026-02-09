'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import {
  Globe,
  Search,
  Wrench,
  Calculator,
  Target,
  Eye,
  Users,
  TrendingUp,
  Check,
  ChevronDown,
  ArrowRight,
  Sparkles,
  Shield,
  Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ScoreRing } from '@/components/shared/score-ring'

/* ─── PRICING DATA ─── */

const plans = [
  {
    name: 'Free',
    monthly: 0,
    yearly: 0,
    description: 'Try it out',
    features: [
      '1 site',
      '1 scan per month',
      'Full score report',
      'Top 3 fix recommendations',
    ],
    cta: 'Start Free',
    highlighted: false,
  },
  {
    name: 'Starter',
    monthly: 49,
    yearly: 39,
    description: 'For growing brands',
    features: [
      '3 sites',
      '10 scans per month',
      '3 competitors per site',
      'Full fix recommendations',
      'Email support',
    ],
    cta: 'Start 14-Day Trial',
    highlighted: false,
  },
  {
    name: 'Professional',
    monthly: 149,
    yearly: 119,
    description: 'For serious teams',
    features: [
      '10 sites',
      '50 scans per month',
      '10 competitors per site',
      'Daily monitoring & alerts',
      'Citation context analysis',
      'Custom questions',
      'Priority support',
    ],
    cta: 'Start 14-Day Trial',
    highlighted: true,
  },
  {
    name: 'Agency',
    monthly: 399,
    yearly: 319,
    description: 'For multi-client teams',
    features: [
      '25 sites',
      '250 scans per month',
      '25 competitors per site',
      'White-label reports',
      'API access',
      '6-hour monitoring',
      'Dedicated support',
    ],
    cta: 'Contact Sales',
    highlighted: false,
  },
]

/* ─── FAQ DATA ─── */

const faqs = [
  {
    q: 'How does the Findable Score work?',
    a: 'We crawl your site, extract content, and simulate how AI answer engines retrieve and process your information. Your score reflects 7 dimensions: technical quality, content structure, schema markup, domain authority, entity recognition, retrieval performance, and coverage.',
  },
  {
    q: "What's the difference between Simulated and Observed scoring?",
    a: "Simulated scoring runs deterministic tests to predict how well AI can source your content. Observed scoring captures real citations from ChatGPT, Perplexity, and Gemini. Together they tell you both what's possible and what's actually happening.",
  },
  {
    q: 'How long does a scan take?',
    a: 'Most sites complete in 3-5 minutes. Larger sites with 50+ pages may take up to 10 minutes. You get real-time progress updates throughout.',
  },
  {
    q: 'Can I compare myself to competitors?',
    a: 'Yes. All paid plans include competitive benchmarking. We run the same questions against your competitors so you can see head-to-head performance across every dimension.',
  },
  {
    q: 'What makes this different from other AI SEO tools?',
    a: "Most tools just monitor whether AI mentions you. We diagnose why and prescribe exactly what to fix. Every fix comes with an estimated point impact so you know what to prioritize.",
  },
  {
    q: 'Do you support custom questions?',
    a: 'Yes. Professional and Agency plans let you add custom \"money questions\" specific to your business\u2014the exact queries your customers are asking AI about.',
  },
]

/* ─── FEATURES DATA ─── */

const features = [
  {
    icon: Calculator,
    title: 'Transparent Scoring',
    description:
      'No black boxes. See exactly how your score is calculated across 7 dimensions with our "Show the Math" breakdown.',
  },
  {
    icon: Wrench,
    title: 'Fix Recommendations',
    description:
      'Not just monitoring. Get prescriptive fixes with estimated point impact: "Add FAQ schema, gain ~8 points."',
  },
  {
    icon: Target,
    title: 'Citation Context',
    description:
      'Understand WHY AI cites you (or doesn\'t) based on your content type and source primacy.',
  },
  {
    icon: Eye,
    title: 'Dual Scoring',
    description:
      'Simulated sourceability tells you what\'s possible. Real observation snapshots show what\'s happening.',
  },
  {
    icon: Users,
    title: 'Competitive Benchmarking',
    description:
      'Head-to-head comparison with competitors. See who\'s winning the AI visibility race question by question.',
  },
  {
    icon: TrendingUp,
    title: 'Daily Monitoring',
    description:
      'Automated alerts when your score drops, competitors overtake you, or AI models change how they cite your content.',
  },
]

/* ─── MOCK PILLAR DATA FOR PREVIEW ─── */

const mockPillars = [
  { name: 'Technical', score: 78, weight: 12 },
  { name: 'Structure', score: 65, weight: 18 },
  { name: 'Schema', score: 42, weight: 13 },
  { name: 'Authority', score: 71, weight: 12 },
  { name: 'Entity', score: 58, weight: 13 },
  { name: 'Retrieval', score: 84, weight: 22 },
  { name: 'Coverage', score: 70, weight: 10 },
]

const mockFixes = [
  { title: 'Add FAQ schema markup', impact: '+8 pts', severity: 'high' as const },
  { title: 'Improve heading hierarchy', impact: '+5 pts', severity: 'medium' as const },
  { title: 'Add structured data for products', impact: '+4 pts', severity: 'medium' as const },
]

/* ─── MAIN COMPONENT ─── */

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false)
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* ─── HEADER ─── */}
      <header
        className={cn(
          'fixed top-0 left-0 right-0 z-50 transition-all duration-300',
          scrolled
            ? 'bg-background/95 backdrop-blur-md border-b border-border/40 shadow-lg shadow-black/10'
            : 'bg-transparent'
        )}
      >
        <div className="mx-auto max-w-7xl flex items-center justify-between px-6 h-16">
          <Link href="/" className="font-serif text-2xl text-primary">
            Findable
          </Link>
          <div className="flex items-center gap-3">
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Sign In
              </Button>
            </Link>
            <Link href="/register">
              <Button size="sm">Get Started</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* ─── HERO ─── */}
      <section className="relative min-h-screen flex items-center overflow-hidden pt-16">
        {/* Background effects */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-primary/15 rounded-full blur-[120px]" />
          <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-accent/15 rounded-full blur-[120px]" />
          <div className="absolute top-1/2 right-1/3 w-[300px] h-[300px] bg-pink-500/10 rounded-full blur-[100px]" />
          <svg className="absolute inset-0 w-full h-full opacity-[0.03]">
            <filter id="hero-noise">
              <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="4" />
            </filter>
            <rect width="100%" height="100%" filter="url(#hero-noise)" />
          </svg>
        </div>

        <div className="mx-auto max-w-7xl px-6 w-full">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            {/* Left: Copy */}
            <div className="max-w-xl">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-primary/30 bg-primary/10 text-primary text-sm font-medium mb-6">
                <Sparkles className="h-3.5 w-3.5" />
                AI Answer Engine Visibility
              </div>

              <h1 className="font-serif text-5xl lg:text-7xl leading-[1.1] tracking-tight mb-6">
                Are You{' '}
                <span className="text-gradient-primary">Findable</span>
                <br />
                by AI?
              </h1>

              <p className="text-lg lg:text-xl text-foreground-muted leading-relaxed mb-8 max-w-lg">
                ChatGPT, Perplexity, and Gemini answer millions of questions every day.
                If they can&apos;t find your content, you&apos;re invisible to the next generation of search.
              </p>

              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                <Link href="/register">
                  <Button size="lg" className="glow-primary text-base h-14 px-8">
                    Get Your Free Score
                    <ArrowRight className="h-4 w-4 ml-1" />
                  </Button>
                </Link>
                <p className="text-sm text-foreground-subtle">
                  No credit card required
                </p>
              </div>
            </div>

            {/* Right: Score Ring Demo */}
            <div className="relative flex items-center justify-center">
              <div className="relative">
                <ScoreRing score={82} size={220} strokeWidth={10} animate showGrade />

                {/* Floating stat cards */}
                <div className="absolute -top-4 -right-4 card-elevated px-3 py-2 rounded-lg animate-float text-sm">
                  <span className="text-foreground-muted">Cited in</span>
                  <span className="font-mono font-bold text-grade-b ml-1.5">15/20</span>
                  <span className="text-foreground-muted ml-1">questions</span>
                </div>

                <div
                  className="absolute -bottom-2 -left-6 card-elevated px-3 py-2 rounded-lg animate-float text-sm"
                  style={{ animationDelay: '2s' }}
                >
                  <span className="text-foreground-muted">Top fix:</span>
                  <span className="text-primary ml-1.5">+8 pts</span>
                </div>

                <div
                  className="absolute top-1/2 -right-10 card-elevated px-3 py-2 rounded-lg animate-float text-sm"
                  style={{ animationDelay: '4s' }}
                >
                  <span className="text-foreground-muted">vs competitor:</span>
                  <span className="text-grade-a ml-1.5 font-mono font-bold">+12</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── SOCIAL PROOF BAR ─── */}
      <section className="border-y border-border/30 bg-background-secondary/50 py-8">
        <div className="mx-auto max-w-7xl px-6">
          <div className="flex flex-col sm:flex-row items-center justify-center gap-6 text-foreground-muted text-sm">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-primary" />
              <span>7-dimension transparent scoring</span>
            </div>
            <div className="hidden sm:block w-px h-4 bg-border" />
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary" />
              <span>Results in under 5 minutes</span>
            </div>
            <div className="hidden sm:block w-px h-4 bg-border" />
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-primary" />
              <span>Prescriptive fixes with impact estimates</span>
            </div>
          </div>
        </div>
      </section>

      {/* ─── PROBLEM STATEMENT ─── */}
      <section className="py-24 px-6">
        <div className="mx-auto max-w-4xl text-center">
          <p className="text-primary font-medium text-sm uppercase tracking-widest mb-4">
            The New Search
          </p>
          <h2 className="font-serif text-4xl lg:text-5xl mb-6">
            AI Is the New Search.
            <br />
            <span className="text-foreground-muted">Most Brands Are Invisible.</span>
          </h2>
          <p className="text-lg text-foreground-muted leading-relaxed max-w-2xl mx-auto mb-12">
            Traditional SEO got you ranking on Google. But that&apos;s not where all the traffic goes anymore.
            AI answer engines cite sources directly&mdash;and most websites aren&apos;t optimized to be one.
          </p>

          <div className="grid sm:grid-cols-3 gap-6">
            {[
              { stat: '40%', label: 'of Gen Z use AI as primary search' },
              { stat: '85%', label: 'of B2B buyers research with AI tools' },
              { stat: '0%', label: 'of most sites optimized for AI citation' },
            ].map((item) => (
              <div
                key={item.label}
                className="card-elevated p-6 rounded-xl"
              >
                <div className="font-mono text-4xl font-bold text-gradient-primary mb-2">
                  {item.stat}
                </div>
                <p className="text-sm text-foreground-muted">{item.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── HOW IT WORKS ─── */}
      <section className="py-24 px-6 bg-background-secondary/30">
        <div className="mx-auto max-w-7xl">
          <div className="text-center mb-16">
            <p className="text-primary font-medium text-sm uppercase tracking-widest mb-4">
              How It Works
            </p>
            <h2 className="font-serif text-4xl lg:text-5xl">
              Three Steps to AI Visibility
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                icon: Globe,
                step: '01',
                title: 'Enter Your URL',
                description:
                  'We crawl your site, extract content, and build a retrieval index\u2014simulating exactly how AI models process your information.',
              },
              {
                icon: Search,
                step: '02',
                title: 'Get Your Score',
                description:
                  'Transparent 0-100 Findable Score with breakdown across 7 pillars. See exactly where you stand and why.',
              },
              {
                icon: Wrench,
                step: '03',
                title: 'Fix & Monitor',
                description:
                  'Actionable fixes with estimated point impact. Monitor daily to track improvements and competitive changes.',
              },
            ].map((item) => {
              const Icon = item.icon
              return (
                <div
                  key={item.step}
                  className="card-elevated p-8 rounded-xl hover-lift"
                >
                  <div className="flex items-center gap-4 mb-4">
                    <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary/10 border border-primary/20">
                      <Icon className="h-6 w-6 text-primary" />
                    </div>
                    <span className="font-mono text-sm text-foreground-subtle">{item.step}</span>
                  </div>
                  <h3 className="font-serif text-xl mb-3">{item.title}</h3>
                  <p className="text-foreground-muted leading-relaxed">{item.description}</p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ─── FEATURES ─── */}
      <section className="py-24 px-6">
        <div className="mx-auto max-w-7xl">
          <div className="text-center mb-16">
            <p className="text-primary font-medium text-sm uppercase tracking-widest mb-4">
              Capabilities
            </p>
            <h2 className="font-serif text-4xl lg:text-5xl mb-4">
              Not Just Monitoring.{' '}
              <span className="text-gradient-primary">A Prescription.</span>
            </h2>
            <p className="text-lg text-foreground-muted max-w-2xl mx-auto">
              Other tools show you a dashboard. We diagnose the problem and tell you exactly how to fix it.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => {
              const Icon = feature.icon
              return (
                <div
                  key={feature.title}
                  className="card-elevated p-6 rounded-xl hover-lift group"
                >
                  <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 mb-4 transition-colors group-hover:bg-primary/20">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="font-semibold text-lg mb-2">{feature.title}</h3>
                  <p className="text-foreground-muted text-sm leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ─── SCORE PREVIEW ─── */}
      <section className="py-24 px-6 bg-background-secondary/50">
        <div className="mx-auto max-w-7xl">
          <div className="text-center mb-16">
            <p className="text-primary font-medium text-sm uppercase tracking-widest mb-4">
              See It In Action
            </p>
            <h2 className="font-serif text-4xl lg:text-5xl mb-4">
              Your AI Visibility Report
            </h2>
            <p className="text-lg text-foreground-muted max-w-2xl mx-auto">
              Every scan produces a comprehensive report with transparent scoring, competitive context, and actionable fixes.
            </p>
          </div>

          <div className="max-w-4xl mx-auto card-elevated rounded-2xl p-8 lg:p-12 border border-border/50">
            <div className="grid lg:grid-cols-[auto_1fr] gap-10 items-start">
              {/* Score Ring */}
              <div className="flex flex-col items-center gap-3">
                <ScoreRing score={67} size={160} strokeWidth={8} animate showGrade />
                <p className="text-sm text-foreground-muted">Findable Score</p>
              </div>

              {/* Pillar Breakdown */}
              <div className="space-y-6">
                <div>
                  <h3 className="font-serif text-lg mb-4">Score Breakdown</h3>
                  <div className="space-y-3">
                    {mockPillars.map((pillar) => (
                      <div key={pillar.name} className="flex items-center gap-3">
                        <span className="text-sm text-foreground-muted w-20 shrink-0">
                          {pillar.name}
                        </span>
                        <div className="flex-1 h-2 rounded-full bg-background-tertiary overflow-hidden">
                          <div
                            className="h-full rounded-full bg-primary transition-all duration-1000"
                            style={{ width: `${pillar.score}%` }}
                          />
                        </div>
                        <span className="font-mono text-sm w-8 text-right">
                          {pillar.score}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Top Fixes Preview */}
                <div>
                  <h3 className="font-serif text-lg mb-3">Top Fixes</h3>
                  <div className="space-y-2">
                    {mockFixes.map((fix) => (
                      <div
                        key={fix.title}
                        className="flex items-center justify-between p-3 rounded-lg bg-background/50 border border-border/30"
                      >
                        <span className="text-sm">{fix.title}</span>
                        <span className="font-mono text-sm text-primary font-medium">
                          {fix.impact}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Blur overlay hint */}
            <div className="mt-8 text-center">
              <Link href="/register">
                <Button variant="outline" className="gap-2">
                  See your full report
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ─── PRICING ─── */}
      <section className="py-24 px-6" id="pricing">
        <div className="mx-auto max-w-7xl">
          <div className="text-center mb-12">
            <p className="text-primary font-medium text-sm uppercase tracking-widest mb-4">
              Pricing
            </p>
            <h2 className="font-serif text-4xl lg:text-5xl mb-4">
              Simple, Transparent Pricing
            </h2>
            <p className="text-lg text-foreground-muted max-w-2xl mx-auto mb-8">
              Start free. Upgrade when you need more sites, scans, or competitive intelligence.
            </p>

            {/* Billing toggle */}
            <div className="inline-flex items-center gap-3 p-1 rounded-full bg-background-secondary border border-border/50">
              <button
                onClick={() => setBillingCycle('monthly')}
                className={cn(
                  'px-4 py-2 rounded-full text-sm font-medium transition-all',
                  billingCycle === 'monthly'
                    ? 'bg-primary text-white shadow-sm'
                    : 'text-foreground-muted hover:text-foreground'
                )}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingCycle('yearly')}
                className={cn(
                  'px-4 py-2 rounded-full text-sm font-medium transition-all',
                  billingCycle === 'yearly'
                    ? 'bg-primary text-white shadow-sm'
                    : 'text-foreground-muted hover:text-foreground'
                )}
              >
                Yearly
                <span className="ml-1.5 text-xs text-primary-light">Save 20%</span>
              </button>
            </div>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {plans.map((plan) => {
              const price = billingCycle === 'monthly' ? plan.monthly : plan.yearly
              return (
                <div
                  key={plan.name}
                  className={cn(
                    'rounded-xl p-6 flex flex-col',
                    plan.highlighted
                      ? 'card-elevated border-primary/50 ring-1 ring-primary/30 glow-primary relative'
                      : 'card-elevated'
                  )}
                >
                  {plan.highlighted && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-primary text-white text-xs font-medium">
                      Most Popular
                    </div>
                  )}

                  <div className="mb-6">
                    <h3 className="font-serif text-xl mb-1">{plan.name}</h3>
                    <p className="text-sm text-foreground-muted">{plan.description}</p>
                  </div>

                  <div className="mb-6">
                    <div className="flex items-baseline gap-1">
                      <span className="font-mono text-4xl font-bold">
                        ${price}
                      </span>
                      {price > 0 && (
                        <span className="text-foreground-muted text-sm">/mo</span>
                      )}
                    </div>
                    {billingCycle === 'yearly' && price > 0 && (
                      <p className="text-xs text-foreground-subtle mt-1">
                        billed annually
                      </p>
                    )}
                  </div>

                  <ul className="space-y-3 mb-8 flex-1">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2 text-sm">
                        <Check className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                        <span className="text-foreground-muted">{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Link href="/register" className="w-full">
                    <Button
                      className="w-full"
                      variant={plan.highlighted ? 'default' : 'outline'}
                    >
                      {plan.cta}
                    </Button>
                  </Link>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ─── FAQ ─── */}
      <section className="py-24 px-6 bg-background-secondary/30">
        <div className="mx-auto max-w-3xl">
          <div className="text-center mb-16">
            <p className="text-primary font-medium text-sm uppercase tracking-widest mb-4">
              FAQ
            </p>
            <h2 className="font-serif text-4xl lg:text-5xl">
              Common Questions
            </h2>
          </div>

          <div className="space-y-2">
            {faqs.map((faq, i) => (
              <div
                key={i}
                className="card-elevated rounded-xl overflow-hidden"
              >
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-center justify-between p-5 text-left"
                >
                  <span className="font-medium pr-4">{faq.q}</span>
                  <ChevronDown
                    className={cn(
                      'h-5 w-5 text-foreground-muted shrink-0 transition-transform duration-200',
                      openFaq === i && 'rotate-180'
                    )}
                  />
                </button>
                <div
                  className={cn(
                    'overflow-hidden transition-all duration-300',
                    openFaq === i ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
                  )}
                >
                  <p className="px-5 pb-5 text-foreground-muted leading-relaxed">
                    {faq.a}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── FINAL CTA ─── */}
      <section className="relative py-24 px-6 overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-accent/10" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/10 rounded-full blur-[150px]" />
        </div>

        <div className="mx-auto max-w-3xl text-center">
          <h2 className="font-serif text-4xl lg:text-5xl mb-6">
            Start Measuring Your
            <br />
            <span className="text-gradient-primary">AI Visibility Today</span>
          </h2>
          <p className="text-lg text-foreground-muted mb-8 max-w-xl mx-auto">
            Join the brands that know exactly where they stand in the age of AI search.
          </p>
          <Link href="/register">
            <Button size="lg" className="glow-primary text-base h-14 px-10">
              Get Your Free Score
              <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          </Link>
          <p className="text-sm text-foreground-subtle mt-4">
            No credit card required &middot; Results in 5 minutes
          </p>
        </div>
      </section>

      {/* ─── FOOTER ─── */}
      <footer className="border-t border-border/30 bg-background-secondary/50 py-16 px-6">
        <div className="mx-auto max-w-7xl">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
            {/* Brand */}
            <div className="col-span-2 md:col-span-1">
              <Link href="/" className="font-serif text-2xl text-primary">
                Findable
              </Link>
              <p className="text-sm text-foreground-muted mt-2 max-w-xs">
                Measure and improve your visibility in AI answer engines.
              </p>
            </div>

            {/* Product */}
            <div>
              <h4 className="font-medium text-sm mb-4">Product</h4>
              <ul className="space-y-2.5 text-sm text-foreground-muted">
                <li>
                  <a href="#pricing" className="hover:text-primary transition-colors">
                    Pricing
                  </a>
                </li>
                <li>
                  <Link href="/register" className="hover:text-primary transition-colors">
                    Free Scan
                  </Link>
                </li>
              </ul>
            </div>

            {/* Company */}
            <div>
              <h4 className="font-medium text-sm mb-4">Company</h4>
              <ul className="space-y-2.5 text-sm text-foreground-muted">
                <li>
                  <a href="mailto:hello@findable.ai" className="hover:text-primary transition-colors">
                    Contact
                  </a>
                </li>
              </ul>
            </div>

            {/* Legal */}
            <div>
              <h4 className="font-medium text-sm mb-4">Legal</h4>
              <ul className="space-y-2.5 text-sm text-foreground-muted">
                <li>
                  <span className="text-foreground-subtle">Privacy Policy</span>
                </li>
                <li>
                  <span className="text-foreground-subtle">Terms of Service</span>
                </li>
              </ul>
            </div>
          </div>

          <div className="border-t border-border/30 pt-8 text-center">
            <p className="text-sm text-foreground-subtle">
              &copy; {new Date().getFullYear()} Findable. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
