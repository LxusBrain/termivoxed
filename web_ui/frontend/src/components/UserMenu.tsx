/**
 * User Menu Component for TermiVoxed
 *
 * Displays user avatar/initials with a dropdown menu for:
 * - Account settings
 * - Subscription info
 * - Logout
 */

import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { User, Settings, CreditCard, LogOut, ChevronDown } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import clsx from 'clsx'

export default function UserMenu() {
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const [photoError, setPhotoError] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const user = useAuthStore((state) => state.user)
  const subscription = useAuthStore((state) => state.subscription)
  const logout = useAuthStore((state) => state.logout)

  // Reset photo error when user changes
  useEffect(() => {
    setPhotoError(false)
  }, [user?.photoUrl])

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Close menu on escape key
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [])

  const handleLogout = async () => {
    setIsOpen(false)
    await logout()
    navigate('/login')
  }

  if (!user) {
    return (
      <Link
        to="/login"
        className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm text-text-secondary hover:text-text-primary hover:bg-terminal-elevated transition-all"
      >
        <User className="w-4 h-4" />
        <span>Sign In</span>
      </Link>
    )
  }

  // Get user initials for avatar
  const getInitials = () => {
    if (user.displayName) {
      return user.displayName
        .split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    }
    if (user.email) {
      return user.email[0].toUpperCase()
    }
    return 'U'
  }

  // Get subscription badge color
  const getSubscriptionColor = () => {
    if (!subscription) return 'bg-gray-500'
    switch (subscription.tier) {
      case 'pro':
      case 'lifetime':
        return 'bg-gradient-to-r from-cyan-500 to-blue-600'
      case 'enterprise':
        return 'bg-gradient-to-r from-purple-500 to-pink-600'
      case 'individual':
      case 'basic':
        return 'bg-green-500'
      case 'free_trial':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getSubscriptionLabel = () => {
    if (!subscription) return 'Free'
    switch (subscription.tier) {
      case 'free_trial': return 'Trial'
      case 'individual': return 'Individual'
      case 'basic': return 'Basic'
      case 'pro': return 'Pro'
      case 'enterprise': return 'Enterprise'
      case 'lifetime': return 'Lifetime'
      default: return 'Free'
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      {/* User button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'flex items-center gap-2 px-2 py-1 rounded-lg transition-all',
          'hover:bg-terminal-elevated border border-transparent',
          isOpen && 'bg-terminal-elevated border-terminal-border'
        )}
      >
        {/* Avatar */}
        {user.photoUrl && !photoError ? (
          <img
            src={user.photoUrl}
            alt={user.displayName || 'User'}
            className="w-7 h-7 rounded-full object-cover border border-terminal-border"
            onError={() => setPhotoError(true)}
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white text-xs font-medium">
            {getInitials()}
          </div>
        )}

        {/* Name (hidden on mobile) */}
        <span className="hidden md:block text-sm text-text-primary max-w-[120px] truncate">
          {user.displayName || user.email?.split('@')[0] || 'User'}
        </span>

        <ChevronDown className={clsx(
          'w-4 h-4 text-text-muted transition-transform',
          isOpen && 'rotate-180'
        )} />
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-terminal-surface border border-terminal-border rounded-xl shadow-xl overflow-hidden z-50">
          {/* User info header */}
          <div className="p-4 border-b border-terminal-border bg-terminal-elevated/50">
            <div className="flex items-center gap-3">
              {user.photoUrl && !photoError ? (
                <img
                  src={user.photoUrl}
                  alt={user.displayName || 'User'}
                  className="w-10 h-10 rounded-full object-cover border border-terminal-border"
                  onError={() => setPhotoError(true)}
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white text-sm font-medium">
                  {getInitials()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">
                  {user.displayName || 'User'}
                </p>
                <p className="text-xs text-text-muted truncate">
                  {user.email}
                </p>
              </div>
            </div>
            {/* Subscription badge */}
            <div className="mt-3 flex items-center gap-2">
              <span className={clsx(
                'text-[10px] font-medium px-2 py-0.5 rounded-full text-white',
                getSubscriptionColor()
              )}>
                {getSubscriptionLabel()}
              </span>
              {subscription?.status === 'trial' && (
                <span className="text-[10px] text-yellow-400">
                  Trial active
                </span>
              )}
            </div>
          </div>

          {/* Menu items */}
          <div className="py-2">
            <Link
              to="/account"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-3 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-terminal-elevated transition-colors"
            >
              <User className="w-4 h-4" />
              <span>Account Settings</span>
            </Link>

            <Link
              to="/account?tab=subscription"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-3 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-terminal-elevated transition-colors"
            >
              <CreditCard className="w-4 h-4" />
              <span>Subscription & Billing</span>
            </Link>

            <Link
              to="/settings"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-3 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-terminal-elevated transition-colors"
            >
              <Settings className="w-4 h-4" />
              <span>App Settings</span>
            </Link>
          </div>

          {/* Logout */}
          <div className="border-t border-terminal-border py-2">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 px-4 py-2.5 text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors w-full"
            >
              <LogOut className="w-4 h-4" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
