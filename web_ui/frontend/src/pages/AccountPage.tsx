/**
 * Account & Billing Page for TermiVoxed
 *
 * Displays:
 * - User profile information
 * - Subscription status and tier
 * - Usage statistics with progress bars
 * - Device management
 * - Billing history
 */

import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAuthStore, selectUser, selectSubscription, selectIsAuthenticated, Device } from '../stores/authStore'

// Types
interface UsageData {
  period: string
  last_updated: string
  exports: {
    current: number
    limit: number
    percentage: number
    duration_minutes: number
    duration_limit_minutes: number
  }
  tts: {
    current_characters: number
    limit_characters: number
    percentage: number
    generations: number
  }
  ai: {
    current: number
    limit: number
    percentage: number
  }
  voice_cloning: {
    current: number
    limit: number
    percentage: number
  }
  storage: {
    current_mb: number
    limit_mb: number
    percentage: number
  }
}

interface Invoice {
  id: string
  date: string
  amount: string
  status: 'paid' | 'pending' | 'failed'
  description: string
  download_url?: string
}

interface SubscriptionDetails {
  plan: string
  status: string
  current_period_start: string
  current_period_end: string
  cancel_at_period_end: boolean
  payment_method?: {
    type: string
    last4?: string
    brand?: string
  }
}

export function AccountPage() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore(selectIsAuthenticated)
  const user = useAuthStore(selectUser)
  const subscription = useAuthStore(selectSubscription)
  const devices = useAuthStore((state) => state.devices)
  const removeDevice = useAuthStore((state) => state.removeDevice)

  const [usage, setUsage] = useState<UsageData | null>(null)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [subscriptionDetails, setSubscriptionDetails] = useState<SubscriptionDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'usage' | 'billing' | 'devices'>('overview')
  const [cancellingSubscription, setCancellingSubscription] = useState(false)

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: { pathname: '/account' } } })
    }
  }, [isAuthenticated, navigate])

  // Fetch data on mount
  useEffect(() => {
    if (isAuthenticated) {
      fetchAccountData()
    }
  }, [isAuthenticated])

  const fetchAccountData = async () => {
    setLoading(true)
    setError(null)

    try {
      // Fetch usage data
      const usageRes = await api.get('/subscription/usage/summary')
      setUsage(usageRes.data)

      // Fetch subscription details
      try {
        const subRes = await api.get('/payments/subscriptions/current')
        setSubscriptionDetails(subRes.data)
      } catch {
        // May not have an active subscription
      }

      // Fetch invoices
      try {
        const invoicesRes = await api.get('/payments/invoices')
        setInvoices(invoicesRes.data.invoices || [])
      } catch {
        // May not have invoices
      }
    } catch (err) {
      console.error('Failed to fetch account data:', err)
      setError('Failed to load account data. Please refresh the page.')
    } finally {
      setLoading(false)
    }
  }

  const handleCancelSubscription = async () => {
    if (!confirm('Are you sure you want to cancel your subscription? You will lose access at the end of the current billing period.')) {
      return
    }

    setCancellingSubscription(true)
    try {
      await api.post('/payments/subscriptions/cancel')
      await fetchAccountData()
      alert('Your subscription has been cancelled. You will retain access until the end of your current billing period.')
    } catch (err) {
      console.error('Failed to cancel subscription:', err)
      alert('Failed to cancel subscription. Please try again or contact support.')
    } finally {
      setCancellingSubscription(false)
    }
  }

  const handleRemoveDevice = async (deviceId: string) => {
    if (!confirm('Remove this device? It will need to log in again to access your account.')) {
      return
    }

    const success = await removeDevice(deviceId)
    if (!success) {
      alert('Failed to remove device. Please try again.')
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  const formatNumber = (num: number) => {
    return num.toLocaleString()
  }

  if (!isAuthenticated) {
    return null // Will redirect
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-400">Loading account...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-900 to-purple-900/20 py-8 px-4">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white">Account Settings</h1>
            <p className="text-gray-400 mt-1">Manage your subscription, usage, and billing</p>
          </div>
          <Link
            to="/"
            className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
          >
            Back to App
          </Link>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
            {error}
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="flex gap-1 mb-8 bg-gray-800/50 rounded-xl p-1 overflow-x-auto">
          {[
            { key: 'overview', label: 'Overview' },
            { key: 'usage', label: 'Usage' },
            { key: 'billing', label: 'Billing' },
            { key: 'devices', label: 'Devices' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as typeof activeTab)}
              className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                activeTab === tab.key
                  ? 'bg-purple-600 text-white shadow-lg'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="space-y-6">
          {activeTab === 'overview' && (
            <OverviewTab
              user={user}
              subscription={subscription}
              subscriptionDetails={subscriptionDetails}
              usage={usage}
              onCancelSubscription={handleCancelSubscription}
              cancellingSubscription={cancellingSubscription}
              formatDate={formatDate}
            />
          )}

          {activeTab === 'usage' && (
            <UsageTab usage={usage} formatNumber={formatNumber} />
          )}

          {activeTab === 'billing' && (
            <BillingTab
              invoices={invoices}
              subscriptionDetails={subscriptionDetails}
              formatDate={formatDate}
            />
          )}

          {activeTab === 'devices' && (
            <DevicesTab
              devices={devices}
              onRemoveDevice={handleRemoveDevice}
              formatDate={formatDate}
            />
          )}
        </div>
      </div>
    </div>
  )
}

// Overview Tab Component
function OverviewTab({
  user,
  subscription,
  subscriptionDetails,
  usage,
  onCancelSubscription,
  cancellingSubscription,
  formatDate,
}: {
  user: ReturnType<typeof selectUser>
  subscription: ReturnType<typeof selectSubscription>
  subscriptionDetails: SubscriptionDetails | null
  usage: UsageData | null
  onCancelSubscription: () => void
  cancellingSubscription: boolean
  formatDate: (date: string) => string
}) {
  return (
    <>
      {/* Profile Card */}
      <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700/50">
        <h2 className="text-lg font-semibold text-white mb-4">Profile</h2>
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-purple-600 rounded-full flex items-center justify-center text-white text-2xl font-bold">
            {user?.displayName?.[0] || user?.email?.[0] || '?'}
          </div>
          <div>
            <p className="text-white font-medium">
              {user?.displayName || 'User'}
            </p>
            <p className="text-gray-400 text-sm">{user?.email}</p>
            {user?.emailVerified && (
              <span className="inline-flex items-center gap-1 text-green-400 text-xs mt-1">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Verified
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Subscription Card */}
      <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700/50">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Subscription</h2>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${
            subscription?.status === 'active' || subscription?.status === 'trial'
              ? 'bg-green-500/20 text-green-400'
              : subscription?.status === 'past_due' || subscription?.status === 'grace_period'
              ? 'bg-yellow-500/20 text-yellow-400'
              : 'bg-red-500/20 text-red-400'
          }`}>
            {subscription?.status?.replace('_', ' ').toUpperCase() || 'UNKNOWN'}
          </span>
        </div>

        <div className="grid md:grid-cols-2 gap-4 mb-6">
          <div>
            <p className="text-gray-400 text-sm">Current Plan</p>
            <p className="text-white font-medium text-lg">
              {subscription?.tier?.replace('_', ' ').toUpperCase() || 'Free'}
            </p>
          </div>
          {subscriptionDetails?.current_period_end && (
            <div>
              <p className="text-gray-400 text-sm">
                {subscriptionDetails.cancel_at_period_end ? 'Access Until' : 'Renews On'}
              </p>
              <p className="text-white font-medium">
                {formatDate(subscriptionDetails.current_period_end)}
              </p>
            </div>
          )}
        </div>

        {subscriptionDetails?.cancel_at_period_end && (
          <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-yellow-400 text-sm">
            Your subscription is set to cancel at the end of the current period.
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <a
            href="https://lxusbrain.com/termivoxed/subscription"
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors inline-flex items-center gap-2"
          >
            {subscription?.tier === 'free_trial' || subscription?.tier === 'expired'
              ? 'Upgrade Now'
              : 'Manage Subscription'}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>

          {subscription?.tier !== 'free_trial' &&
            subscription?.tier !== 'expired' &&
            !subscriptionDetails?.cancel_at_period_end && (
              <button
                onClick={onCancelSubscription}
                disabled={cancellingSubscription}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {cancellingSubscription ? 'Cancelling...' : 'Cancel Subscription'}
              </button>
            )}
        </div>
      </div>

      {/* Quick Usage Summary */}
      {usage && (
        <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700/50">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Usage This Month</h2>
            <span className="text-gray-400 text-sm">{usage.period}</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <UsageQuickStat
              label="Exports"
              current={usage.exports.current}
              limit={usage.exports.limit}
              percentage={usage.exports.percentage}
            />
            <UsageQuickStat
              label="TTS Characters"
              current={usage.tts.current_characters}
              limit={usage.tts.limit_characters}
              percentage={usage.tts.percentage}
              format="compact"
            />
            <UsageQuickStat
              label="AI Requests"
              current={usage.ai.current}
              limit={usage.ai.limit}
              percentage={usage.ai.percentage}
            />
            <UsageQuickStat
              label="Storage"
              current={usage.storage.current_mb}
              limit={usage.storage.limit_mb}
              percentage={usage.storage.percentage}
              suffix="MB"
            />
          </div>
        </div>
      )}
    </>
  )
}

// Usage Quick Stat Component
function UsageQuickStat({
  label,
  current,
  limit,
  percentage,
  suffix = '',
  format = 'number',
}: {
  label: string
  current: number
  limit: number
  percentage: number
  suffix?: string
  format?: 'number' | 'compact'
}) {
  const formatValue = (val: number) => {
    if (format === 'compact') {
      if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`
      if (val >= 1000) return `${(val / 1000).toFixed(1)}K`
    }
    return val.toLocaleString()
  }

  return (
    <div>
      <p className="text-gray-400 text-xs mb-1">{label}</p>
      <p className="text-white font-medium">
        {formatValue(current)}{suffix} <span className="text-gray-500">/ {formatValue(limit)}{suffix}</span>
      </p>
      <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            percentage >= 90
              ? 'bg-red-500'
              : percentage >= 70
              ? 'bg-yellow-500'
              : 'bg-purple-500'
          }`}
          style={{ width: `${Math.min(100, percentage)}%` }}
        />
      </div>
    </div>
  )
}

// Usage Tab Component
function UsageTab({
  usage,
  formatNumber,
}: {
  usage: UsageData | null
  formatNumber: (num: number) => string
}) {
  if (!usage) {
    return (
      <div className="text-center py-12 text-gray-400">
        Usage data not available
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Period Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Usage for {usage.period}</h2>
        <p className="text-gray-400 text-sm">
          Last updated: {new Date(usage.last_updated).toLocaleString()}
        </p>
      </div>

      {/* Usage Cards */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Exports */}
        <UsageCard
          title="Video Exports"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" />
            </svg>
          }
          current={usage.exports.current}
          limit={usage.exports.limit}
          percentage={usage.exports.percentage}
          formatNumber={formatNumber}
          details={[
            { label: 'Total Duration', value: `${usage.exports.duration_minutes.toFixed(1)} / ${usage.exports.duration_limit_minutes} min` },
          ]}
        />

        {/* TTS */}
        <UsageCard
          title="Text-to-Speech"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
          }
          current={usage.tts.current_characters}
          limit={usage.tts.limit_characters}
          percentage={usage.tts.percentage}
          formatNumber={formatNumber}
          suffix=" chars"
          details={[
            { label: 'Generations', value: formatNumber(usage.tts.generations) },
          ]}
        />

        {/* AI Requests */}
        <UsageCard
          title="AI Generations"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          }
          current={usage.ai.current}
          limit={usage.ai.limit}
          percentage={usage.ai.percentage}
          formatNumber={formatNumber}
          suffix=" requests"
        />

        {/* Voice Cloning */}
        <UsageCard
          title="Voice Cloning"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          }
          current={usage.voice_cloning.current}
          limit={usage.voice_cloning.limit}
          percentage={usage.voice_cloning.percentage}
          formatNumber={formatNumber}
          suffix=" clones"
        />

        {/* Storage */}
        <UsageCard
          title="Storage"
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
            </svg>
          }
          current={usage.storage.current_mb}
          limit={usage.storage.limit_mb}
          percentage={usage.storage.percentage}
          formatNumber={formatNumber}
          suffix=" MB"
        />
      </div>
    </div>
  )
}

// Usage Card Component
function UsageCard({
  title,
  icon,
  current,
  limit,
  percentage,
  formatNumber,
  suffix = '',
  details = [],
}: {
  title: string
  icon: React.ReactNode
  current: number
  limit: number
  percentage: number
  formatNumber: (num: number) => string
  suffix?: string
  details?: { label: string; value: string }[]
}) {
  return (
    <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700/50">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-purple-500/20 rounded-lg text-purple-400">
          {icon}
        </div>
        <h3 className="text-white font-medium">{title}</h3>
      </div>

      <div className="mb-4">
        <div className="flex items-end gap-2">
          <span className="text-3xl font-bold text-white">{formatNumber(current)}</span>
          <span className="text-gray-400 mb-1">/ {formatNumber(limit)}{suffix}</span>
        </div>
        <div className="mt-3 h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              percentage >= 90
                ? 'bg-red-500'
                : percentage >= 70
                ? 'bg-yellow-500'
                : 'bg-purple-500'
            }`}
            style={{ width: `${Math.min(100, percentage)}%` }}
          />
        </div>
        <p className="text-gray-400 text-sm mt-2">
          {percentage.toFixed(1)}% used • {formatNumber(Math.max(0, limit - current))}{suffix} remaining
        </p>
      </div>

      {details.length > 0 && (
        <div className="pt-4 border-t border-gray-700/50 space-y-2">
          {details.map((detail) => (
            <div key={detail.label} className="flex justify-between text-sm">
              <span className="text-gray-400">{detail.label}</span>
              <span className="text-gray-300">{detail.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Billing Tab Component
function BillingTab({
  invoices,
  subscriptionDetails,
  formatDate,
}: {
  invoices: Invoice[]
  subscriptionDetails: SubscriptionDetails | null
  formatDate: (date: string) => string
}) {
  return (
    <div className="space-y-6">
      {/* Payment Method */}
      {subscriptionDetails?.payment_method && (
        <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700/50">
          <h2 className="text-lg font-semibold text-white mb-4">Payment Method</h2>
          <div className="flex items-center gap-4">
            <div className="p-3 bg-gray-700 rounded-lg">
              <svg className="w-6 h-6 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
              </svg>
            </div>
            <div>
              <p className="text-white font-medium">
                {subscriptionDetails.payment_method.brand?.toUpperCase() || 'Card'} ending in {subscriptionDetails.payment_method.last4}
              </p>
              <p className="text-gray-400 text-sm">
                {subscriptionDetails.payment_method.type === 'card' ? 'Credit/Debit Card' : subscriptionDetails.payment_method.type}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Invoice History */}
      <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700/50">
        <h2 className="text-lg font-semibold text-white mb-4">Invoice History</h2>

        {invoices.length === 0 ? (
          <p className="text-gray-400 text-center py-8">
            No invoices yet. Your billing history will appear here.
          </p>
        ) : (
          <div className="space-y-3">
            {invoices.map((invoice) => (
              <div
                key={invoice.id}
                className="flex items-center justify-between p-4 bg-gray-700/30 rounded-lg"
              >
                <div>
                  <p className="text-white font-medium">{invoice.description}</p>
                  <p className="text-gray-400 text-sm">{formatDate(invoice.date)}</p>
                </div>
                <div className="flex items-center gap-4">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    invoice.status === 'paid'
                      ? 'bg-green-500/20 text-green-400'
                      : invoice.status === 'pending'
                      ? 'bg-yellow-500/20 text-yellow-400'
                      : 'bg-red-500/20 text-red-400'
                  }`}>
                    {invoice.status.toUpperCase()}
                  </span>
                  <span className="text-white font-medium">{invoice.amount}</span>
                  {invoice.download_url && (
                    <a
                      href={invoice.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-purple-400 hover:text-purple-300 transition-colors"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Devices Tab Component
function DevicesTab({
  devices,
  onRemoveDevice,
  formatDate,
}: {
  devices: Device[]
  onRemoveDevice: (deviceId: string) => void
  formatDate: (date: string) => string
}) {
  return (
    <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700/50">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Active Devices</h2>
        <span className="text-gray-400 text-sm">
          {devices.length} device{devices.length !== 1 ? 's' : ''} registered
        </span>
      </div>

      {devices.length === 0 ? (
        <p className="text-gray-400 text-center py-8">
          No devices registered yet.
        </p>
      ) : (
        <div className="space-y-3">
          {devices.map((device) => (
            <div
              key={device.deviceId}
              className={`flex items-center justify-between p-4 rounded-lg ${
                device.isCurrent
                  ? 'bg-purple-500/10 border border-purple-500/30'
                  : 'bg-gray-700/30'
              }`}
            >
              <div className="flex items-center gap-4">
                <div className="p-2 bg-gray-700 rounded-lg">
                  <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    {device.deviceType === 'mobile' ? (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    ) : (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    )}
                  </svg>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-white font-medium">{device.deviceName}</p>
                    {device.isCurrent && (
                      <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded-full">
                        This device
                      </span>
                    )}
                  </div>
                  <p className="text-gray-400 text-sm">
                    {device.osVersion || 'Unknown OS'} • Last active {formatDate(device.lastSeen)}
                  </p>
                </div>
              </div>

              {!device.isCurrent && (
                <button
                  onClick={() => onRemoveDevice(device.deviceId)}
                  className="p-2 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                  title="Remove device"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <p className="mt-4 text-gray-500 text-sm">
        Remove devices you no longer use to keep your account secure.
      </p>
    </div>
  )
}

export default AccountPage
