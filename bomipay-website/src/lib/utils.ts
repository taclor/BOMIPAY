import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Convert minor units (kobo) to formatted NGN string */
export function formatNGN(minor: number): string {
  return `₦${(minor / 100).toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

/** Convert basis points to percentage string */
export function bpsToPercent(bps: number): string {
  return `${(bps / 100).toFixed(2)}%`
}

/** Format ISO date to Lagos timezone */
export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-NG', { timeZone: 'Africa/Lagos' })
}

/** Format ISO date to short date */
export function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-NG', {
    timeZone: 'Africa/Lagos',
    month: 'short',
    day: 'numeric',
  })
}

/** Format ISO date to relative time */
export function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

/** Truncate text with ellipsis */
export function truncate(text: string, length: number): string {
  if (text.length <= length) return text
  return text.slice(0, length) + '…'
}

/** Get severity color class */
export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical': return 'text-red-500'
    case 'high': return 'text-orange-500'
    case 'medium': return 'text-yellow-500'
    case 'low': return 'text-blue-500'
    default: return 'text-gray-400'
  }
}

/** Get status color class */
export function getStatusColor(status: string): string {
  switch (status) {
    case 'open': return 'text-red-400'
    case 'acknowledged': return 'text-yellow-400'
    case 'investigating': return 'text-orange-400'
    case 'resolved': return 'text-green-400'
    case 'healthy': return 'text-green-400'
    case 'degraded': return 'text-yellow-400'
    case 'down': return 'text-red-400'
    case 'matched': return 'text-green-400'
    case 'mismatched': return 'text-red-400'
    case 'pending': return 'text-gray-400'
    case 'unmatched': return 'text-orange-400'
    default: return 'text-gray-400'
  }
}
