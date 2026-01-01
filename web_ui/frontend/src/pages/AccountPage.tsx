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
import { motion } from 'framer-motion'
import { useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft,
  User,
  CreditCard,
  Activity,
  Laptop,
  Crown,
  Zap,
  Sparkles,
  CheckCircle,
  Loader2,
  Trash2,
  LogOut,
  ExternalLink
} from 'lucide-react'
import { api } from '../api/client'
import { useAuthStore, selectUser, selectSubscription, selectIsAuthenticated, Device } from '../stores/authStore'
import { cn } from '../lib/utils'
import { TermiVoxedLogo, LxusBrainLogo } from '../components/logos'

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
  amount: number
  currency: string
  status: string
  invoiceNumber: string
  createdAt: string
  downloadUrl?: string
  // For compatibility
  plan?: string
  period?: string
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

// Animation variants
const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay: i * 0.1, ease: [0.25, 0.4, 0.25, 1] }
  })
}

export function AccountPage() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore(selectIsAuthenticated)
  const user = useAuthStore(selectUser)
  const subscription = useAuthStore(selectSubscription)
  const devices = useAuthStore((state) => state.devices)
  const removeDevice = useAuthStore((state) => state.removeDevice)
  const logout = useAuthStore((state) => state.logout)

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

  const handleLogout = async () => {
    await logout()
    navigate('/login')
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

  // Plan colors and icons
  const planColors: Record<string, string> = {
    free_trial: 'from-gray-500 to-gray-600',
    basic: 'from-cyan-500 to-blue-600',
    individual: 'from-cyan-500 to-blue-600',
    pro: 'from-violet-500 to-purple-600',
    enterprise: 'from-amber-500 to-orange-600',
    lifetime: 'from-emerald-500 to-green-600',
    expired: 'from-red-500 to-red-600'
  }

  const planIcons: Record<string, React.ElementType> = {
    free_trial: Sparkles,
    basic: Zap,
    individual: Zap,
    pro: Crown,
    enterprise: Crown,
    lifetime: Crown,
    expired: Sparkles
  }

  const currentTier = subscription?.tier || 'free_trial'
  const PlanIcon = planIcons[currentTier] || Sparkles

  if (!isAuthenticated) {
    return null // Will redirect
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-neutral-950 flex items-center justify-center">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <TermiVoxedLogo width={80} />
          <p className="text-zinc-400">Loading...</p>
        </div>
      </div>
    )
  }

  const tabs = [
    { key: 'overview', label: 'Overview', icon: User },
    { key: 'usage', label: 'Usage', icon: Activity },
    { key: 'billing', label: 'Billing', icon: CreditCard },
    { key: 'devices', label: 'Devices', icon: Laptop },
  ]

  return (
    <div className="min-h-screen bg-neutral-950 relative overflow-hidden">
      {/* Background gradient effect */}
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(6,182,212,0.15),rgba(255,255,255,0))]" />

      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-neutral-950/80 backdrop-blur-xl border-b border-white/[0.08]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="text-sm">Back to App</span>
              </button>
            </div>
            <Link to="/" className="flex items-center gap-3">
              <TermiVoxedLogo width={40} />
            </Link>
            <div className="flex items-center gap-4">
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors text-sm"
              >
                <LogOut className="w-4 h-4" />
                <span className="hidden sm:inline">Sign out</span>
              </button>
              {/* User Avatar */}
              {user?.photoUrl ? (
                <img
                  src={user.photoUrl}
                  alt={user.displayName || 'User'}
                  className="w-8 h-8 rounded-full border border-cyan-500/30"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
                  <span className="text-xs font-bold text-white">
                    {(user?.displayName || user?.email || 'U')[0].toUpperCase()}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      <main className="pt-24 pb-16 px-4 relative z-10">
        <div className="max-w-5xl mx-auto">
          {/* Header */}
          <motion.div
            custom={0}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            className="mb-8"
          >
            <h1 className="text-2xl sm:text-3xl font-bold text-white mb-2">
              Account <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500">Settings</span>
            </h1>
            <p className="text-zinc-400">Manage your subscription, usage, and billing</p>
          </motion.div>

          {error && (
            <motion.div
              custom={0.5}
              variants={fadeUp}
              initial="hidden"
              animate="visible"
              className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400"
            >
              {error}
            </motion.div>
          )}

          {/* Navigation Tabs */}
          <motion.div
            custom={1}
            variants={fadeUp}
            initial="hidden"
            animate="visible"
            className="flex gap-1 mb-8 bg-white/[0.02] rounded-xl p-1 overflow-x-auto border border-white/[0.08]"
          >
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key as typeof activeTab)}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap",
                    activeTab === tab.key
                      ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg'
                      : 'text-zinc-400 hover:text-white'
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              )
            })}
          </motion.div>

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
                currentTier={currentTier}
                PlanIcon={PlanIcon}
                planColors={planColors}
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
      </main>

      {/* Footer */}
      <footer className="py-8 px-4 border-t border-white/[0.05] relative z-10">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <LxusBrainLogo size={16} />
            <span className="text-zinc-500 text-xs">
              &copy; {new Date().getFullYear()} LxusBrain
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <a href="https://lxusbrain.com/legal/terms" target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-white transition">Terms</a>
            <a href="https://lxusbrain.com/legal/privacy" target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-white transition">Privacy</a>
            <a href="mailto:lxusbrain@gmail.com" className="text-zinc-500 hover:text-white transition">Contact</a>
          </div>
        </div>
      </footer>
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
  currentTier,
  PlanIcon,
  planColors,
}: {
  user: ReturnType<typeof selectUser>
  subscription: ReturnType<typeof selectSubscription>
  subscriptionDetails: SubscriptionDetails | null
  usage: UsageData | null
  onCancelSubscription: () => void
  cancellingSubscription: boolean
  formatDate: (date: string) => string
  currentTier: string
  PlanIcon: React.ElementType
  planColors: Record<string, string>
}) {
  return (
    <>
      {/* Profile Card */}
      <motion.div
        custom={2}
        variants={fadeUp}
        initial="hidden"
        animate="visible"
        className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08]"
      >
        <div className="flex items-center gap-3 mb-6">
          <User className="w-5 h-5 text-cyan-400" />
          <h2 className="text-lg font-semibold text-white">Profile</h2>
        </div>
        <div className="flex items-center gap-4">
          <div className="relative">
            {user?.photoUrl ? (
              <img
                src={user.photoUrl}
                alt={user.displayName || 'User'}
                className="w-16 h-16 rounded-full border-2 border-cyan-500/30"
              />
            ) : (
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
                <span className="text-2xl font-bold text-white">
                  {(user?.displayName || user?.email || 'U')[0].toUpperCase()}
                </span>
              </div>
            )}
            <div className={cn(
              "absolute -bottom-1 -right-1 p-1 rounded-full bg-gradient-to-r",
              planColors[currentTier] || planColors.free_trial
            )}>
              <PlanIcon className="w-3 h-3 text-white" />
            </div>
          </div>
          <div>
            <p className="text-white font-medium">
              {user?.displayName || 'User'}
            </p>
            <p className="text-zinc-400 text-sm">{user?.email}</p>
            {user?.emailVerified && (
              <span className="inline-flex items-center gap-1 text-green-400 text-xs mt-1">
                <CheckCircle className="w-3 h-3" />
                Verified
              </span>
            )}
          </div>
        </div>
      </motion.div>

      {/* Subscription Card */}
      <motion.div
        custom={3}
        variants={fadeUp}
        initial="hidden"
        animate="visible"
        className="p-6 rounded-2xl bg-gradient-to-br from-cyan-950/30 via-slate-900/50 to-blue-950/30 border border-cyan-500/20"
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <CreditCard className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">Subscription</h2>
          </div>
          <span className={cn(
            "px-3 py-1 rounded-full text-xs font-medium",
            subscription?.status === 'active' || subscription?.status === 'trial'
              ? 'bg-green-500/20 text-green-400 border border-green-500/30'
              : subscription?.status === 'past_due' || subscription?.status === 'grace_period'
              ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
              : 'bg-red-500/20 text-red-400 border border-red-500/30'
          )}>
            {subscription?.status?.replace('_', ' ').toUpperCase() || 'UNKNOWN'}
          </span>
        </div>

        <div className="grid sm:grid-cols-3 gap-4 mb-6">
          <div>
            <p className="text-xs text-zinc-500 mb-1">Current Plan</p>
            <p className={cn(
              "font-medium capitalize bg-clip-text text-transparent bg-gradient-to-r",
              planColors[currentTier] || planColors.free_trial
            )}>
              {currentTier.replace('_', ' ')}
            </p>
          </div>
          {subscriptionDetails?.current_period_end && (
            <div>
              <p className="text-xs text-zinc-500 mb-1">
                {subscriptionDetails.cancel_at_period_end ? 'Access Until' : 'Renews On'}
              </p>
              <p className="text-white font-medium">
                {formatDate(subscriptionDetails.current_period_end)}
              </p>
            </div>
          )}
          <div>
            <p className="text-xs text-zinc-500 mb-1">Billing Period</p>
            <p className="text-white font-medium">Monthly</p>
          </div>
        </div>

        {subscriptionDetails?.cancel_at_period_end && (
          <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-yellow-400 text-sm">
            Your subscription is set to cancel at the end of the current period.
          </div>
        )}

        <div className="flex flex-wrap gap-3 pt-4 border-t border-white/[0.08]">
          <a
            href="https://lxusbrain.com/termivoxed/subscription"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white rounded-lg font-medium transition-all inline-flex items-center gap-2"
          >
            {subscription?.tier === 'free_trial' || subscription?.tier === 'expired'
              ? 'Upgrade Now'
              : 'Manage Subscription'}
            <ExternalLink className="w-4 h-4" />
          </a>

          {subscription?.tier !== 'free_trial' &&
            subscription?.tier !== 'expired' &&
            !subscriptionDetails?.cancel_at_period_end && (
              <button
                onClick={onCancelSubscription}
                disabled={cancellingSubscription}
                className="px-4 py-2.5 bg-white/[0.05] hover:bg-white/[0.08] border border-white/[0.08] text-zinc-300 rounded-lg font-medium transition-all disabled:opacity-50 flex items-center gap-2"
              >
                {cancellingSubscription ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Cancelling...
                  </>
                ) : (
                  'Cancel Subscription'
                )}
              </button>
            )}
        </div>
      </motion.div>

      {/* Quick Usage Summary */}
      {usage && (
        <motion.div
          custom={4}
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08]"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <Activity className="w-5 h-5 text-cyan-400" />
              <h2 className="text-lg font-semibold text-white">Usage This Month</h2>
            </div>
            <span className="text-zinc-500 text-sm">{usage.period}</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
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
        </motion.div>
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
    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.05]">
      <p className="text-zinc-500 text-xs mb-1">{label}</p>
      <p className="text-white font-medium text-lg">
        {formatValue(current)}{suffix}
      </p>
      <p className="text-zinc-500 text-xs">/ {formatValue(limit)}{suffix}</p>
      <div className="mt-2 h-1.5 bg-white/[0.05] rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            percentage >= 90
              ? 'bg-red-500'
              : percentage >= 70
              ? 'bg-yellow-500'
              : 'bg-gradient-to-r from-cyan-500 to-blue-500'
          )}
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
      <motion.div
        custom={2}
        variants={fadeUp}
        initial="hidden"
        animate="visible"
        className="text-center py-12 text-zinc-400"
      >
        Usage data not available
      </motion.div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Period Header */}
      <motion.div
        custom={2}
        variants={fadeUp}
        initial="hidden"
        animate="visible"
        className="flex items-center justify-between"
      >
        <h2 className="text-lg font-semibold text-white">Usage for {usage.period}</h2>
        <p className="text-zinc-500 text-sm">
          Last updated: {new Date(usage.last_updated).toLocaleString()}
        </p>
      </motion.div>

      {/* Usage Cards */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Exports */}
        <UsageCard
          title="Video Exports"
          icon={<Activity className="w-5 h-5" />}
          current={usage.exports.current}
          limit={usage.exports.limit}
          percentage={usage.exports.percentage}
          formatNumber={formatNumber}
          details={[
            { label: 'Total Duration', value: `${usage.exports.duration_minutes.toFixed(1)} / ${usage.exports.duration_limit_minutes} min` },
          ]}
          delay={3}
        />

        {/* TTS */}
        <UsageCard
          title="Text-to-Speech"
          icon={<Activity className="w-5 h-5" />}
          current={usage.tts.current_characters}
          limit={usage.tts.limit_characters}
          percentage={usage.tts.percentage}
          formatNumber={formatNumber}
          suffix=" chars"
          details={[
            { label: 'Generations', value: formatNumber(usage.tts.generations) },
          ]}
          delay={4}
        />

        {/* AI Requests */}
        <UsageCard
          title="AI Generations"
          icon={<Sparkles className="w-5 h-5" />}
          current={usage.ai.current}
          limit={usage.ai.limit}
          percentage={usage.ai.percentage}
          formatNumber={formatNumber}
          suffix=" requests"
          delay={5}
        />

        {/* Voice Cloning */}
        <UsageCard
          title="Voice Cloning"
          icon={<User className="w-5 h-5" />}
          current={usage.voice_cloning.current}
          limit={usage.voice_cloning.limit}
          percentage={usage.voice_cloning.percentage}
          formatNumber={formatNumber}
          suffix=" clones"
          delay={6}
        />

        {/* Storage */}
        <UsageCard
          title="Storage"
          icon={<Activity className="w-5 h-5" />}
          current={usage.storage.current_mb}
          limit={usage.storage.limit_mb}
          percentage={usage.storage.percentage}
          formatNumber={formatNumber}
          suffix=" MB"
          delay={7}
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
  delay = 0,
}: {
  title: string
  icon: React.ReactNode
  current: number
  limit: number
  percentage: number
  formatNumber: (num: number) => string
  suffix?: string
  details?: { label: string; value: string }[]
  delay?: number
}) {
  return (
    <motion.div
      custom={delay}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08]"
    >
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-cyan-500/10 rounded-lg text-cyan-400">
          {icon}
        </div>
        <h3 className="text-white font-medium">{title}</h3>
      </div>

      <div className="mb-4">
        <div className="flex items-end gap-2">
          <span className="text-3xl font-bold text-white">{formatNumber(current)}</span>
          <span className="text-zinc-500 mb-1">/ {formatNumber(limit)}{suffix}</span>
        </div>
        <div className="mt-3 h-2 bg-white/[0.05] rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              percentage >= 90
                ? 'bg-red-500'
                : percentage >= 70
                ? 'bg-yellow-500'
                : 'bg-gradient-to-r from-cyan-500 to-blue-500'
            )}
            style={{ width: `${Math.min(100, percentage)}%` }}
          />
        </div>
        <p className="text-zinc-500 text-sm mt-2">
          {percentage.toFixed(1)}% used • {formatNumber(Math.max(0, limit - current))}{suffix} remaining
        </p>
      </div>

      {details.length > 0 && (
        <div className="pt-4 border-t border-white/[0.05] space-y-2">
          {details.map((detail) => (
            <div key={detail.label} className="flex justify-between text-sm">
              <span className="text-zinc-500">{detail.label}</span>
              <span className="text-zinc-300">{detail.value}</span>
            </div>
          ))}
        </div>
      )}
    </motion.div>
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
        <motion.div
          custom={2}
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08]"
        >
          <div className="flex items-center gap-3 mb-4">
            <CreditCard className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">Payment Method</h2>
          </div>
          <div className="flex items-center gap-4">
            <div className="p-3 bg-white/[0.05] rounded-lg">
              <CreditCard className="w-6 h-6 text-zinc-300" />
            </div>
            <div>
              <p className="text-white font-medium">
                {subscriptionDetails.payment_method.brand?.toUpperCase() || 'Card'} ending in {subscriptionDetails.payment_method.last4}
              </p>
              <p className="text-zinc-500 text-sm">
                {subscriptionDetails.payment_method.type === 'card' ? 'Credit/Debit Card' : subscriptionDetails.payment_method.type}
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Invoice History */}
      <motion.div
        custom={3}
        variants={fadeUp}
        initial="hidden"
        animate="visible"
        className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08]"
      >
        <div className="flex items-center gap-3 mb-4">
          <Activity className="w-5 h-5 text-cyan-400" />
          <h2 className="text-lg font-semibold text-white">Invoice History</h2>
        </div>

        {invoices.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-zinc-500 mb-2">No invoices yet</p>
            <p className="text-sm text-zinc-600">
              Your billing history will appear here after your first payment
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {invoices.map((invoice) => {
              const currencySymbol = invoice.currency === 'INR' ? '₹' : '$'
              const formattedAmount = `${currencySymbol}${(invoice.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
              const invoiceDate = invoice.createdAt ? formatDate(invoice.createdAt) : 'N/A'
              const description = invoice.invoiceNumber ? `Invoice #${invoice.invoiceNumber}` : `Payment ${invoice.id.slice(0, 8)}`

              return (
                <div
                  key={invoice.id}
                  className="flex items-center justify-between p-4 rounded-lg bg-white/[0.02] border border-white/[0.05] hover:border-white/[0.1] transition-colors"
                >
                  <div>
                    <p className="text-white font-medium">{description}</p>
                    <p className="text-zinc-500 text-sm">{invoiceDate}</p>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className={cn(
                      "px-2 py-1 rounded text-xs font-medium",
                      invoice.status === 'paid'
                        ? 'bg-green-500/20 text-green-400'
                        : invoice.status === 'pending'
                        ? 'bg-yellow-500/20 text-yellow-400'
                        : 'bg-red-500/20 text-red-400'
                    )}>
                      {(invoice.status || 'unknown').toUpperCase()}
                    </span>
                    <span className="text-white font-medium">{formattedAmount}</span>
                    {invoice.downloadUrl && (
                      <a
                        href={invoice.downloadUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-cyan-400 hover:text-cyan-300 transition-colors"
                      >
                        <ExternalLink className="w-5 h-5" />
                      </a>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </motion.div>
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
    <motion.div
      custom={2}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.08]"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Laptop className="w-5 h-5 text-cyan-400" />
          <h2 className="text-lg font-semibold text-white">Active Devices</h2>
        </div>
        <span className="text-zinc-500 text-sm">
          {devices.length} device{devices.length !== 1 ? 's' : ''} registered
        </span>
      </div>

      {devices.length === 0 ? (
        <p className="text-zinc-500 text-center py-8">
          No devices registered yet.
        </p>
      ) : (
        <div className="space-y-3">
          {devices.map((device) => (
            <div
              key={device.deviceId}
              className={cn(
                "flex items-center justify-between p-4 rounded-lg",
                device.isCurrent
                  ? 'bg-cyan-500/10 border border-cyan-500/30'
                  : 'bg-white/[0.02] border border-white/[0.05]'
              )}
            >
              <div className="flex items-center gap-4">
                <div className="p-2 bg-white/[0.05] rounded-lg">
                  <Laptop className="w-5 h-5 text-zinc-300" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-white font-medium">{device.deviceName}</p>
                    {device.isCurrent && (
                      <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-400 text-xs rounded-full border border-cyan-500/30">
                        This device
                      </span>
                    )}
                  </div>
                  <p className="text-zinc-500 text-sm">
                    {device.osVersion || 'Unknown OS'} • Last active {formatDate(device.lastSeen)}
                  </p>
                </div>
              </div>

              {!device.isCurrent && (
                <button
                  onClick={() => onRemoveDevice(device.deviceId)}
                  className="p-2 text-zinc-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                  title="Remove device"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <p className="mt-4 text-zinc-600 text-sm">
        Remove devices you no longer use to keep your account secure.
      </p>
    </motion.div>
  )
}

export default AccountPage
