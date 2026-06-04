'use client'

import { useState, FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { Activity, Lock, Mail, Eye, EyeOff } from 'lucide-react'
import { login } from '@/lib/auth'
import { useAuthStore } from '@/store/authStore'

export default function LoginPage() {
  const router = useRouter()
  const { setAuth } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const data = await login({ email, password })
      setAuth(data.access_token, data.user)
      router.push('/dashboard')
    } catch {
      setError('Invalid credentials. Check email and password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0e1a] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded bg-blue-600/20 border border-blue-600/40 mb-4">
            <Activity className="w-6 h-6 text-blue-400" />
          </div>
          <h1 className="text-xl font-bold text-white tracking-wider uppercase">BomiPay</h1>
          <p className="text-xs text-gray-500 mt-1 tracking-widest uppercase">Operations Intelligence</p>
        </div>

        {/* Card */}
        <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
          <h2 className="text-sm font-semibold text-gray-300 mb-6 uppercase tracking-wider">Sign In</h2>

          {error && (
            <div className="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded text-xs text-red-400">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-600" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="ops@merchant.com"
                  className="w-full bg-[#0a0e1a] border border-[#1f2937] rounded px-9 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500/50 font-mono"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-600" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="w-full bg-[#0a0e1a] border border-[#1f2937] rounded px-9 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500/50 font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400"
                >
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {loading ? 'Authenticating…' : 'Sign In'}
            </button>
          </form>
        </div>

        <p className="text-center text-[10px] text-gray-600 mt-4">
          BomiPay OpsIntel v1.0 · Internal Use Only
        </p>
      </div>
    </div>
  )
}
