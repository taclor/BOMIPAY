'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Building2,
  Globe,
  CreditCard,
  Upload,
  CheckCircle,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  FileText,
} from 'lucide-react'
import { getToken } from '@/lib/auth'

interface BusinessProfile {
  company_name: string
  industry: string
  country: string
}

interface Provider {
  provider_name: string
  environment: 'test' | 'live'
  public_key: string
  secret_key: string
  webhook_secret: string
}

interface BankAccount {
  bank_name: string
  account_number: string
  account_holder_name: string
  purpose: 'settlement' | 'payout'
}

type Step = 'business' | 'provider' | 'bank' | 'statement' | 'complete'

export default function OnboardingPage() {
  const router = useRouter()
  const [currentStep, setCurrentStep] = useState<Step>('business')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [merchantId, setMerchantId] = useState<string>('')
  const [showSecrets, setShowSecrets] = useState({ secret: false, webhook: false })

  const [businessProfile, setBusinessProfile] = useState<BusinessProfile>({
    company_name: '',
    industry: '',
    country: '',
  })

  const [provider, setProvider] = useState<Provider>({
    provider_name: 'paystack',
    environment: 'test',
    public_key: '',
    secret_key: '',
    webhook_secret: '',
  })

  const [bankAccount, setBankAccount] = useState<BankAccount>({
    bank_name: '',
    account_number: '',
    account_holder_name: '',
    purpose: 'settlement',
  })

  const [testConnectionStatus, setTestConnectionStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle')

  useEffect(() => {
    const user = localStorage.getItem('user')
    const merchantIdFromStorage = localStorage.getItem('merchant_id')
    if (!user || !merchantIdFromStorage) {
      router.push('/login')
    }
  }, [router])

  useEffect(() => {
    const merchantIdFromStorage = localStorage.getItem('merchant_id')
    if (merchantIdFromStorage) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMerchantId(merchantIdFromStorage)
    }
  }, [])

  const handleBusinessSubmit = async () => {
    if (!businessProfile.company_name || !businessProfile.industry || !businessProfile.country) {
      setError('Please fill all fields')
      return
    }

    setLoading(true)
    setError('')
    try {
      const token = getToken()
      const response = await fetch(`http://localhost:8082/api/v1/merchants/${merchantId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: businessProfile.company_name,
          business_type: businessProfile.industry,
          country: businessProfile.country,
        }),
      })

      if (!response.ok) throw new Error('Failed to update business profile')
      setCurrentStep('provider')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save profile')
    } finally {
      setLoading(false)
    }
  }

  const handleTestConnection = async () => {
    setTestConnectionStatus('testing')
    try {
      const token = getToken()
      const response = await fetch('http://localhost:8082/api/v1/providers/connect', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          merchant_id: merchantId,
          provider_name: provider.provider_name,
          credentials: {
            api_key: provider.public_key,
            secret_key: provider.secret_key,
          },
        }),
      })

      if (!response.ok) throw new Error('Connection test failed')
      setTestConnectionStatus('success')
      setTimeout(() => setTestConnectionStatus('idle'), 2000)
    } catch (_err) {
      // Error is intentionally unused as we just update UI state
      setTestConnectionStatus('error')
      setTimeout(() => setTestConnectionStatus('idle'), 2000)
    }
  }

  const handleProviderSubmit = async () => {
    if (!provider.public_key || !provider.secret_key || !provider.webhook_secret) {
      setError('Please fill all provider fields')
      return
    }

    setLoading(true)
    setError('')
    try {
      const token = getToken()
      const response = await fetch('http://localhost:8082/api/v1/providers/connect', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          merchant_id: merchantId,
          provider_name: provider.provider_name,
          credentials: {
            api_key: provider.public_key,
            secret_key: provider.secret_key,
          },
        }),
      })

      if (!response.ok) throw new Error('Failed to save provider')
      setCurrentStep('bank')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save provider')
    } finally {
      setLoading(false)
    }
  }

  const handleBankSubmit = async () => {
    if (!bankAccount.bank_name || !bankAccount.account_number || !bankAccount.account_holder_name) {
      setError('Please fill all bank fields')
      return
    }

    setLoading(true)
    setError('')
    try {
      const token = getToken()
      const response = await fetch(`http://localhost:8082/api/v1/bank-accounts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          merchant_id: merchantId,
          bank_name: bankAccount.bank_name,
          account_number: bankAccount.account_number,
          account_name: bankAccount.account_holder_name,
          purpose: bankAccount.purpose,
        }),
      })

      if (!response.ok) throw new Error('Failed to save bank account')
      setCurrentStep('statement')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save bank account')
    } finally {
      setLoading(false)
    }
  }

  const handleSkipStatement = async () => {
    setCurrentStep('complete')
  }

  const handleUploadStatement = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setLoading(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('merchant_id', merchantId)

      const token = getToken()
      const response = await fetch(`http://localhost:8082/api/v1/bank_statements/upload`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      })

      if (!response.ok) throw new Error('Failed to upload bank statement')
      setCurrentStep('complete')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload statement')
    } finally {
      setLoading(false)
    }
  }

  const goToDashboard = () => {
    router.push('/dashboard')
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Complete Your Setup</h1>
          <p className="text-gray-600">Let&apos;s get your payment operations ready</p>
        </div>

        {/* Progress Steps */}
        <div className="mb-8 flex justify-between">
          {[
            { step: 'business', label: 'Business', icon: Building2 },
            { step: 'provider', label: 'Provider', icon: Globe },
            { step: 'bank', label: 'Bank', icon: CreditCard },
            { step: 'statement', label: 'Statement', icon: Upload },
            { step: 'complete', label: 'Complete', icon: CheckCircle },
          ].map((s, i) => {
            const Icon = s.icon
            const isActive = currentStep === s.step
            const isCompleted =
              ['business', 'provider', 'bank', 'statement'].indexOf(currentStep) >
              ['business', 'provider', 'bank', 'statement'].indexOf(s.step as Step)

            return (
              <div key={s.step} className="flex flex-col items-center flex-1">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 ${
                    isActive ? 'bg-blue-600 text-white' : isCompleted ? 'bg-green-600 text-white' : 'bg-gray-300 text-gray-600'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <p className={`text-xs font-medium ${isActive || isCompleted ? 'text-gray-900' : 'text-gray-500'}`}>
                  {s.label}
                </p>
                {i < 4 && (
                  <div
                    className={`absolute w-20 h-0.5 mt-5 ml-12 ${
                      isCompleted ? 'bg-green-600' : 'bg-gray-300'
                    }`}
                  />
                )}
              </div>
            )
          })}
        </div>

        {/* Step 1: Business Profile */}
        {currentStep === 'business' && (
          <div className="bg-white rounded-xl shadow-sm p-8 border border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-6">Business Profile</h2>
            {error && (
              <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Company Name</label>
                <input
                  type="text"
                  value={businessProfile.company_name}
                  onChange={(e) =>
                    setBusinessProfile({ ...businessProfile, company_name: e.target.value })
                  }
                  placeholder="Acme Corp"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Industry</label>
                <select
                  value={businessProfile.industry}
                  onChange={(e) =>
                    setBusinessProfile({ ...businessProfile, industry: e.target.value })
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select industry</option>
                  <option value="saas">SaaS</option>
                  <option value="retail">Retail</option>
                  <option value="fintech">Fintech</option>
                  <option value="ecommerce">E-commerce</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Country</label>
                <input
                  type="text"
                  value={businessProfile.country}
                  onChange={(e) =>
                    setBusinessProfile({ ...businessProfile, country: e.target.value })
                  }
                  placeholder="Nigeria"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <button
                onClick={handleBusinessSubmit}
                disabled={loading}
                className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Saving...' : 'Continue'}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Provider */}
        {currentStep === 'provider' && (
          <div className="bg-white rounded-xl shadow-sm p-8 border border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-6">Connect Payment Provider</h2>
            {error && (
              <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Payment Provider
                </label>
                <select
                  value={provider.provider_name}
                  onChange={(e) =>
                    setProvider({ ...provider, provider_name: e.target.value })
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="paystack">Paystack</option>
                  <option value="flutterwave">Flutterwave</option>
                  <option value="monnify">Monnify</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Environment
                </label>
                <select
                  value={provider.environment}
                  onChange={(e) =>
                    setProvider({ ...provider, environment: e.target.value as 'test' | 'live' })
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="test">Test (Development)</option>
                  <option value="live">Live (Production)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Public Key</label>
                <input
                  type="text"
                  value={provider.public_key}
                  onChange={(e) =>
                    setProvider({ ...provider, public_key: e.target.value })
                  }
                  placeholder="pk_test_..."
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Secret Key</label>
                <div className="relative">
                  <input
                    type={showSecrets.secret ? 'text' : 'password'}
                    value={provider.secret_key}
                    onChange={(e) =>
                      setProvider({ ...provider, secret_key: e.target.value })
                    }
                    placeholder="sk_test_..."
                    className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setShowSecrets({ ...showSecrets, secret: !showSecrets.secret })
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400"
                  >
                    {showSecrets.secret ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Webhook Secret
                </label>
                <div className="relative">
                  <input
                    type={showSecrets.webhook ? 'text' : 'password'}
                    value={provider.webhook_secret}
                    onChange={(e) =>
                      setProvider({ ...provider, webhook_secret: e.target.value })
                    }
                    placeholder="whsec_..."
                    className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setShowSecrets({ ...showSecrets, webhook: !showSecrets.webhook })
                    }
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400"
                  >
                    {showSecrets.webhook ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
              <button
                onClick={handleTestConnection}
                disabled={testConnectionStatus === 'testing'}
                className={`w-full py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  testConnectionStatus === 'success'
                    ? 'bg-green-100 text-green-700'
                    : testConnectionStatus === 'error'
                      ? 'bg-red-100 text-red-700'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {testConnectionStatus === 'testing' ? (
                  <>
                    <Loader2 className="w-4 h-4 inline mr-2 animate-spin" />
                    Testing...
                  </>
                ) : testConnectionStatus === 'success' ? (
                  '✓ Connection OK'
                ) : testConnectionStatus === 'error' ? (
                  '✗ Connection Failed'
                ) : (
                  'Test Connection'
                )}
              </button>
              <button
                onClick={handleProviderSubmit}
                disabled={loading}
                className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Saving...' : 'Continue'}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Bank Account */}
        {currentStep === 'bank' && (
          <div className="bg-white rounded-xl shadow-sm p-8 border border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-6">Bank Account Details</h2>
            {error && (
              <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Bank Name
                </label>
                <input
                  type="text"
                  value={bankAccount.bank_name}
                  onChange={(e) =>
                    setBankAccount({ ...bankAccount, bank_name: e.target.value })
                  }
                  placeholder="Zenith Bank"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Account Number
                </label>
                <input
                  type="text"
                  value={bankAccount.account_number}
                  onChange={(e) =>
                    setBankAccount({ ...bankAccount, account_number: e.target.value })
                  }
                  placeholder="1234567890"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Account Holder Name
                </label>
                <input
                  type="text"
                  value={bankAccount.account_holder_name}
                  onChange={(e) =>
                    setBankAccount({
                      ...bankAccount,
                      account_holder_name: e.target.value,
                    })
                  }
                  placeholder="Acme Corp Ltd"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Purpose</label>
                <select
                  value={bankAccount.purpose}
                  onChange={(e) =>
                    setBankAccount({
                      ...bankAccount,
                      purpose: e.target.value as 'settlement' | 'payout',
                    })
                  }
                  className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="settlement">Settlement (Receive payments)</option>
                  <option value="payout">Payout (Send funds)</option>
                </select>
              </div>
              <button
                onClick={handleBankSubmit}
                disabled={loading}
                className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Saving...' : 'Continue'}
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Bank Statement */}
        {currentStep === 'statement' && (
          <div className="bg-white rounded-xl shadow-sm p-8 border border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-6">Upload Bank Statement</h2>
            <p className="text-sm text-gray-600 mb-6">
              Upload a bank statement to help us reconcile transactions (optional)
            </p>
            {error && (
              <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}
            <div className="space-y-4">
              <label className="flex items-center justify-center w-full px-4 py-8 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50">
                <div className="flex flex-col items-center">
                  <FileText className="w-8 h-8 text-gray-400 mb-2" />
                  <span className="text-sm font-medium text-gray-700">
                    Upload CSV or Excel file
                  </span>
                  <span className="text-xs text-gray-500 mt-1">
                    Drag & drop or click to select
                  </span>
                </div>
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleUploadStatement}
                  disabled={loading}
                  className="hidden"
                />
              </label>
              <div className="flex gap-3">
                <button
                  onClick={handleSkipStatement}
                  className="flex-1 py-2.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium transition-colors"
                >
                  Skip for now
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 5: Complete */}
        {currentStep === 'complete' && (
          <div className="bg-white rounded-xl shadow-sm p-8 border border-gray-200 text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-green-600" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Setup Complete!</h2>
            <p className="text-gray-600 mb-6">
              Your payment operations are ready. You can now view your dashboard and start
              monitoring transactions.
            </p>
            <button
              onClick={goToDashboard}
              className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors"
            >
              Go to Dashboard
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
