'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Shell from '@/components/layout/Shell'
import ProviderHealthCard from '@/components/providers/ProviderHealthCard'
import { listProviders } from '@/lib/provider'

interface Provider {
  provider_account_id: string
  provider_name: string
  merchant_id: string
  status: string
}

export default function ProvidersPage() {
  const router = useRouter()
  const [providers, setProviders] = useState<Provider[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadProviders = async () => {
    try {
      setLoading(true)
      const data = await listProviders()
      setProviders(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load providers')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProviders()
  }, [])

  const handleDisconnected = () => {
    loadProviders()
  }

  if (loading) {
    return (
      <Shell title="Payment Providers">
        <div className="flex items-center justify-center h-96">
          <p className="text-gray-500">Loading providers...</p>
        </div>
      </Shell>
    )
  }

  if (error) {
    return (
      <Shell title="Payment Providers">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700">{error}</p>
        </div>
      </Shell>
    )
  }

  return (
    <Shell title="Payment Providers" onRefresh={loadProviders}>
      {providers.length === 0 ? (
        // Empty State
        <div className="flex flex-col items-center justify-center h-96 bg-white rounded-lg border border-gray-200">
          <p className="text-4xl mb-3">🔗</p>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            No providers connected
          </h2>
          <p className="text-gray-600 text-center max-w-md mb-6">
            Start by connecting a payment provider to sync transactions and track
            settlement data.
          </p>
          <button
            onClick={() => router.push('/providers/connect')}
            className="px-6 py-2 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-600 transition-colors"
          >
            Connect Your First Provider
          </button>
        </div>
      ) : (
        // Provider List
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                {providers.length} {providers.length === 1 ? 'Provider' : 'Providers'} Connected
              </h2>
            </div>
            <button
              onClick={() => router.push('/providers/connect')}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-600 transition-colors"
            >
              Add Another Provider
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {providers.map((provider) => (
              <ProviderHealthCard
                key={provider.provider_account_id}
                id={provider.provider_account_id}
                provider_name={provider.provider_name}
                status={provider.status}
                onDisconnected={handleDisconnected}
              />
            ))}
          </div>
        </div>
      )}
    </Shell>
  )
}

