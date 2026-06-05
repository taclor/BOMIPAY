'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Shell from '@/components/layout/Shell'
import { testConnection, connectProvider } from '@/lib/provider'

export default function ConnectProviderPage() {
  const router = useRouter()
  const [provider, setProvider] = useState('paystack')
  const [environment, setEnvironment] = useState<'test' | 'live'>('test')
  const [publicKey, setPublicKey] = useState('')
  const [secretKey, setSecretKey] = useState('')
  const [webhookSecret, setWebhookSecret] = useState('')
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{
    success: boolean
    message?: string
  } | null>(null)

  const handleTestConnection = async () => {
    if (!publicKey || !secretKey) {
      setError('Public Key and Secret Key are required')
      return
    }

    setTesting(true)
    setError(null)
    setTestResult(null)

    try {
      const result = await testConnection({
        provider_name: provider,
        public_key: publicKey,
        secret_key: secretKey,
        webhook_secret: webhookSecret || undefined,
      })
      setTestResult(result)
      if (!result.success) {
        setError(result.message || 'Connection test failed')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection test failed')
    } finally {
      setTesting(false)
    }
  }

  const handleConnect = async () => {
    if (!publicKey || !secretKey) {
      setError('Public Key and Secret Key are required')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const result = await connectProvider({
        provider_name: provider,
        public_key: publicKey,
        secret_key: secretKey,
        webhook_secret: webhookSecret || undefined,
        environment,
      })
      if (result.success) {
        router.push('/providers')
      } else {
        setError('Failed to connect provider')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect provider')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Shell title="Connect Payment Provider">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          <div className="space-y-6">
            {/* Provider Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Payment Provider
              </label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                disabled={loading || testing}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
              >
                <option value="paystack">Paystack</option>
                <option value="flutterwave">Flutterwave</option>
                <option value="monnify">Monnify</option>
              </select>
            </div>

            {/* Environment Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Environment
              </label>
              <div className="grid grid-cols-2 gap-4">
                {(['test', 'live'] as const).map((env) => (
                  <button
                    key={env}
                    onClick={() => setEnvironment(env)}
                    disabled={loading || testing}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 ${
                      environment === env
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {env === 'test' ? 'Test' : 'Live'}
                  </button>
                ))}
              </div>
            </div>

            {/* Public Key */}
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Public Key
              </label>
              <input
                type="text"
                value={publicKey}
                onChange={(e) => setPublicKey(e.target.value)}
                disabled={loading || testing}
                placeholder="Enter your public key"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
              />
            </div>

            {/* Secret Key */}
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Secret Key
              </label>
              <input
                type="password"
                value={secretKey}
                onChange={(e) => setSecretKey(e.target.value)}
                disabled={loading || testing}
                placeholder="Enter your secret key"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
              />
            </div>

            {/* Webhook Secret */}
            <div>
              <label className="block text-sm font-medium text-gray-900 mb-2">
                Webhook Secret (Optional)
              </label>
              <input
                type="password"
                value={webhookSecret}
                onChange={(e) => setWebhookSecret(e.target.value)}
                disabled={loading || testing}
                placeholder="Enter your webhook secret"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
              />
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Test Result */}
            {testResult && (
              <div
                className={`p-3 border rounded-lg ${
                  testResult.success
                    ? 'bg-green-50 border-green-200'
                    : 'bg-yellow-50 border-yellow-200'
                }`}
              >
                <p
                  className={`text-sm ${
                    testResult.success ? 'text-green-700' : 'text-yellow-700'
                  }`}
                >
                  {testResult.success ? '✓ Connection successful!' : '⚠ ' + testResult.message}
                </p>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3 pt-4">
              <button
                onClick={handleTestConnection}
                disabled={loading || testing || !publicKey || !secretKey}
                className="flex-1 px-4 py-2 bg-gray-100 text-gray-900 rounded-lg font-medium hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {testing ? 'Testing...' : 'Test Connection'}
              </button>
              <button
                onClick={handleConnect}
                disabled={loading || testing || !publicKey || !secretKey}
                className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'Connecting...' : 'Connect'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Shell>
  )
}
