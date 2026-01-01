/**
 * Pricing Page for TermiVoxed
 *
 * Displays subscription tiers with multi-currency support:
 * - INR for India (Razorpay)
 * - USD for International (Stripe)
 *
 * Styled to match the LxusBrain website theme.
 */

import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuthStore, selectIsAuthenticated } from '../stores/authStore'
import { TermiVoxedLogo } from '../components/logos'

// Types
interface PriceData {
  price: number
  formatted: string
  per_day?: string
  monthly_equivalent?: string
  savings_percent: number
}

interface PlanPrices {
  monthly?: PriceData
  quarterly?: PriceData
  yearly?: PriceData
}

interface PlanLimits {
  exports_per_month: number
  max_video_duration_minutes: number
  max_projects: number
  max_devices: number
  tts_minutes_per_month: number
  ai_generations_per_month: number
  features: string[]
}

interface Plan {
  name: string
  description: string
  recommended?: boolean
  contact_sales?: boolean
  per_seat_price?: number
  per_seat_formatted?: string
  price?: number
  period?: string
  prices?: PlanPrices
  limits: PlanLimits
}

interface PricingData {
  currency: string
  currency_symbol: string
  processor: string
  gst_included: boolean
  gst_percent: number
  plans: {
    free_trial: Plan
    individual: Plan
    pro: Plan
    enterprise: Plan
  }
}

type BillingPeriod = 'monthly' | 'quarterly' | 'yearly'

// Feature display names
const FEATURE_NAMES: Record<string, string> = {
  basic_export: 'Basic Export',
  subtitle_generation: 'Auto Subtitles',
  basic_tts_voices: 'Cloud TTS Voices',
  export_720p: '720p Export',
  export_1080p: '1080p Export',
  multi_video_projects: 'Multi-Video Projects',
  custom_fonts: 'Custom Fonts',
  basic_bgm: 'Background Music',
  advanced_tts_voices: 'Premium TTS Voices',
  multiple_bgm_tracks: 'Multiple BGM Tracks',
  export_4k: '4K Export',
  batch_export: 'Batch Export',
  custom_subtitle_styles: 'Custom Subtitle Styles',
  cross_video_segments: 'Cross-Video Segments',
  voice_cloning: 'Voice Cloning',
  priority_support: 'Priority Support',
  sso: 'Single Sign-On (SSO)',
  team_management: 'Team Management',
  api_access: 'API Access',
  custom_branding: 'Custom Branding',
}

export function PricingPage() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore(selectIsAuthenticated)
  const [pricing, setPricing] = useState<PricingData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>('yearly')
  const [processingPlan, setProcessingPlan] = useState<string | null>(null)

  // Fetch pricing on mount
  useEffect(() => {
    fetchPricing()
  }, [])

  const fetchPricing = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await api.get('/payments/pricing')
      setPricing(response.data)
    } catch (err) {
      console.error('Failed to fetch pricing:', err)
      setError('Failed to load pricing. Please refresh the page.')
    } finally {
      setLoading(false)
    }
  }

  const handleSubscribe = async (plan: string) => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: { pathname: '/pricing' } } })
      return
    }

    // Handle free trial - start trial directly
    if (plan === 'free_trial') {
      setProcessingPlan(plan)
      try {
        await api.post('/payments/subscriptions/start-trial')
        // Refresh user data and redirect
        navigate('/payment/success?trial=true')
      } catch (err: unknown) {
        const errorMessage = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        setError(errorMessage || 'Failed to start free trial. Please try again.')
      } finally {
        setProcessingPlan(null)
      }
      return
    }

    if (plan === 'enterprise') {
      // Redirect to contact form for enterprise
      window.location.href = 'mailto:lxusbrain@gmail.com?subject=TermiVoxed Enterprise Inquiry'
      return
    }

    setProcessingPlan(plan)

    try {
      const response = await api.post('/payments/subscriptions/create', {
        plan,
        period: billingPeriod,
        currency: pricing?.currency,
      })

      const data = response.data

      if (data.checkout_url) {
        // Stripe - redirect to checkout
        window.location.href = data.checkout_url
      } else if (data.subscription_id && data.key_id) {
        // Razorpay - open payment modal
        openRazorpayCheckout(data)
      }
    } catch (err) {
      console.error('Subscription error:', err)
      setError('Failed to start checkout. Please try again.')
    } finally {
      setProcessingPlan(null)
    }
  }

  const openRazorpayCheckout = (data: {
    subscription_id: string
    key_id: string
    amount: number
    plan: string
  }) => {
    // Load Razorpay script if not already loaded
    if (!(window as unknown as { Razorpay: unknown }).Razorpay) {
      const script = document.createElement('script')
      script.src = 'https://checkout.razorpay.com/v1/checkout.js'
      script.onload = () => initRazorpay(data)
      document.body.appendChild(script)
    } else {
      initRazorpay(data)
    }
  }

  const initRazorpay = (data: {
    subscription_id: string
    key_id: string
    amount: number
    plan: string
  }) => {
    const options = {
      key: data.key_id,
      subscription_id: data.subscription_id,
      name: 'TermiVoxed',
      description: `${data.plan.charAt(0).toUpperCase() + data.plan.slice(1)} Plan`,
      handler: () => {
        // Payment successful - redirect to success page
        navigate('/payment/success')
      },
      prefill: {
        email: useAuthStore.getState().user?.email,
      },
      theme: {
        color: '#06b6d4', // Cyan
      },
    }

    const rzp = new (window as unknown as { Razorpay: new (options: unknown) => { open: () => void } }).Razorpay(options)
    rzp.open()
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-400">Loading pricing...</p>
        </div>
      </div>
    )
  }

  if (error || !pricing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a]">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error || 'Failed to load pricing'}</p>
          <button
            onClick={fetchPricing}
            className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white rounded-xl"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const { plans, currency, gst_included, processor } = pricing

  return (
    <div className="min-h-screen bg-[#0a0a0a] py-12 px-4 relative overflow-hidden">
      {/* Background gradient effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-[600px] h-[600px] bg-cyan-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-blue-600/5 rounded-full blur-3xl" />
      </div>

      <div className="max-w-7xl mx-auto relative z-10">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-block">
            <TermiVoxedLogo width={120} />
          </Link>
        </div>

        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Simple, Transparent <span className="bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">Pricing</span>
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto">
            Choose the plan that fits your needs. Start with a free trial,
            upgrade anytime.
          </p>

          {/* Currency indicator */}
          <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-gray-900/50 backdrop-blur-sm rounded-full text-sm text-gray-300 border border-white/10">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            Paying in {currency} via {processor === 'razorpay' ? 'Razorpay' : 'Stripe'}
            {gst_included && <span className="text-gray-500">• GST included</span>}
          </div>
        </div>

        {/* Billing period toggle */}
        <div className="flex justify-center mb-12">
          <div className="inline-flex bg-gray-900/50 backdrop-blur-sm rounded-xl p-1 border border-white/10">
            {(['monthly', 'quarterly', 'yearly'] as BillingPeriod[]).map((period) => (
              <button
                key={period}
                onClick={() => setBillingPeriod(period)}
                className={`px-6 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  billingPeriod === period
                    ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/25'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {period.charAt(0).toUpperCase() + period.slice(1)}
                {period === 'yearly' && (
                  <span className="ml-2 px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full">
                    Save 16%
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Pricing cards */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Free Trial */}
          <PricingCard
            plan={plans.free_trial}
            planKey="free_trial"
            billingPeriod={billingPeriod}
            onSubscribe={handleSubscribe}
            processing={processingPlan === 'free_trial'}
            isFree
          />

          {/* Individual */}
          <PricingCard
            plan={plans.individual}
            planKey="individual"
            billingPeriod={billingPeriod}
            onSubscribe={handleSubscribe}
            processing={processingPlan === 'individual'}
          />

          {/* Pro - Recommended */}
          <PricingCard
            plan={plans.pro}
            planKey="pro"
            billingPeriod={billingPeriod}
            onSubscribe={handleSubscribe}
            processing={processingPlan === 'pro'}
            highlighted
          />

          {/* Enterprise */}
          <PricingCard
            plan={plans.enterprise}
            planKey="enterprise"
            billingPeriod={billingPeriod}
            onSubscribe={handleSubscribe}
            processing={processingPlan === 'enterprise'}
            isEnterprise
          />
        </div>

        {/* FAQ or additional info */}
        <div className="mt-16 text-center">
          <p className="text-gray-400">
            Questions?{' '}
            <a href="mailto:lxusbrain@gmail.com" className="text-cyan-400 hover:underline">
              Contact us
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}

// Pricing Card Component
function PricingCard({
  plan,
  planKey,
  billingPeriod,
  onSubscribe,
  processing,
  highlighted,
  isFree,
  isEnterprise,
}: {
  plan: Plan
  planKey: string
  billingPeriod: BillingPeriod
  onSubscribe: (plan: string) => void
  processing: boolean
  highlighted?: boolean
  isFree?: boolean
  isEnterprise?: boolean
}) {
  const priceData = plan.prices?.[billingPeriod]
  const displayPrice = priceData?.formatted || (isFree ? 'Free' : 'Contact Us')

  return (
    <div
      className={`relative rounded-2xl p-6 backdrop-blur-sm transition-all ${
        highlighted
          ? 'bg-gradient-to-b from-cyan-950/50 to-blue-950/50 border-2 border-cyan-500/50 shadow-lg shadow-cyan-500/10'
          : 'bg-gray-900/50 border border-white/10 hover:border-cyan-500/30'
      }`}
    >
      {/* Recommended badge */}
      {plan.recommended && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="px-3 py-1 bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-xs font-medium rounded-full shadow-lg shadow-cyan-500/25">
            Most Popular
          </span>
        </div>
      )}

      {/* Plan name */}
      <h3 className="text-xl font-semibold text-white mb-2">{plan.name}</h3>
      <p className="text-gray-400 text-sm mb-4">{plan.description}</p>

      {/* Price */}
      <div className="mb-6">
        {isFree ? (
          <div className="text-3xl font-bold text-white">Free</div>
        ) : isEnterprise ? (
          <div>
            <div className="text-3xl font-bold text-white">{displayPrice}</div>
            {plan.per_seat_formatted && (
              <p className="text-sm text-gray-400 mt-1">
                + {plan.per_seat_formatted}/user/month
              </p>
            )}
          </div>
        ) : (
          <div>
            <div className="text-3xl font-bold text-white">{displayPrice}</div>
            {priceData?.per_day && (
              <p className="text-sm text-gray-400 mt-1">
                Just {priceData.per_day}/day
              </p>
            )}
            {priceData?.monthly_equivalent && billingPeriod !== 'monthly' && (
              <p className="text-sm text-gray-400 mt-1">
                {priceData.monthly_equivalent}/month
              </p>
            )}
            {priceData && priceData.savings_percent > 0 && (
              <p className="text-sm text-green-400 mt-1">
                Save {priceData.savings_percent}%
              </p>
            )}
          </div>
        )}
      </div>

      {/* CTA Button */}
      <button
        onClick={() => onSubscribe(planKey)}
        disabled={processing}
        className={`w-full py-3 px-4 rounded-xl font-medium transition-all flex items-center justify-center gap-2 ${
          highlighted
            ? 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white shadow-lg shadow-cyan-500/25'
            : isFree
            ? 'bg-gray-800/50 hover:bg-gray-800 text-white border border-gray-700'
            : 'bg-gray-800/50 hover:bg-gray-800 text-white border border-gray-700 hover:border-cyan-500/50'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        {processing ? (
          <>
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Processing...
          </>
        ) : isFree ? (
          'Start Free Trial'
        ) : isEnterprise ? (
          'Contact Sales'
        ) : (
          'Subscribe'
        )}
      </button>

      {/* Feature list */}
      <div className="mt-6 pt-6 border-t border-gray-700/50">
        <p className="text-sm font-medium text-gray-300 mb-3">Includes:</p>
        <ul className="space-y-2">
          {/* Limits */}
          <li className="flex items-center gap-2 text-sm text-gray-400">
            <CheckIcon />
            {plan.limits.exports_per_month} exports/month
          </li>
          <li className="flex items-center gap-2 text-sm text-gray-400">
            <CheckIcon />
            {plan.limits.max_video_duration_minutes} min max video
          </li>
          <li className="flex items-center gap-2 text-sm text-gray-400">
            <CheckIcon />
            {plan.limits.tts_minutes_per_month} TTS minutes/month
          </li>
          <li className="flex items-center gap-2 text-sm text-gray-400">
            <CheckIcon />
            {plan.limits.max_devices} device{plan.limits.max_devices > 1 ? 's' : ''}
          </li>

          {/* Features */}
          {plan.limits.features.slice(0, 5).map((feature) => (
            <li key={feature} className="flex items-center gap-2 text-sm text-gray-400">
              <CheckIcon />
              {FEATURE_NAMES[feature] || feature}
            </li>
          ))}

          {plan.limits.features.length > 5 && (
            <li className="text-sm text-cyan-400">
              + {plan.limits.features.length - 5} more features
            </li>
          )}
        </ul>
      </div>
    </div>
  )
}

function CheckIcon() {
  return (
    <svg
      className="w-4 h-4 text-cyan-400 flex-shrink-0"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

export default PricingPage
