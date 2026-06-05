import { useState } from 'react'
import { disconnectProvider } from '@/lib/provider'

interface ProviderHealthCardProps {
  id: string
  provider_name: string
  status: string
  last_sync?: string
  transaction_count?: number
  settlement_count?: number
  onDisconnected?: () => void
}

export default function ProviderHealthCard({
  id,
  provider_name,
  status,
  last_sync,
  transaction_count = 0,
  settlement_count = 0,
  onDisconnected,
}: ProviderHealthCardProps) {
  const [loading, setLoading] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const getStatusBadge = () => {
    switch (status) {
      case 'active':
      case 'healthy':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
            ✅ Healthy
          </span>
        )
      case 'degraded':
      case 'needs_attention':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
            ⚠️ Needs Attention
          </span>
        )
      case 'disconnected':
      case 'inactive':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
            ❌ Disconnected
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
            ❓ Unknown
          </span>
        )
    }
  }

  const getProviderLogo = () => {
    switch (provider_name.toLowerCase()) {
      case 'paystack':
        return '🏦'
      case 'flutterwave':
        return '🌊'
      case 'monnify':
        return '💳'
      default:
        return '💰'
    }
  }

  const handleDisconnect = async () => {
    if (!showConfirm) {
      setShowConfirm(true)
      return
    }

    setLoading(true)
    try {
      await disconnectProvider(id)
      onDisconnected?.()
    } catch (err) {
      console.error('Failed to disconnect provider:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{getProviderLogo()}</span>
          <div>
            <h3 className="text-base font-semibold text-gray-900 capitalize">
              {provider_name}
            </h3>
            <p className="text-xs text-gray-500">Provider Account</p>
          </div>
        </div>
        {getStatusBadge()}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 py-3 border-t border-b border-gray-100">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider">Transactions</p>
          <p className="text-lg font-semibold text-gray-900 mt-1">{transaction_count}</p>
          <p className="text-xs text-gray-400">This week</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider">Settlements</p>
          <p className="text-lg font-semibold text-gray-900 mt-1">{settlement_count}</p>
          <p className="text-xs text-gray-400">This week</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider">Last Sync</p>
          <p className="text-lg font-semibold text-gray-900 mt-1">
            {last_sync ? new Date(last_sync).toLocaleTimeString('en-NG', { timeZone: 'Africa/Lagos' }) : '-'}
          </p>
          <p className="text-xs text-gray-400">
            {last_sync ? new Date(last_sync).toLocaleDateString('en-NG', { timeZone: 'Africa/Lagos' }) : 'Never'}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <button className="flex-1 px-3 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors">
          View Details
        </button>
        {showConfirm ? (
          <>
            <button
              onClick={() => setShowConfirm(false)}
              disabled={loading}
              className="px-3 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleDisconnect}
              disabled={loading}
              className="px-3 py-2 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 disabled:opacity-50"
            >
              {loading ? 'Disconnecting...' : 'Confirm'}
            </button>
          </>
        ) : (
          <button
            onClick={handleDisconnect}
            disabled={loading}
            className="px-3 py-2 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 disabled:opacity-50"
          >
            Disconnect
          </button>
        )}
      </div>
    </div>
  )
}
