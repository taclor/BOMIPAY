'use client'

import { useState, FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { Activity, User, Mail, Phone, Lock, Eye, EyeOff } from 'lucide-react'
import { register } from '@/lib/auth'

interface FormState {
  fullName: string
  email: string
  phone: string
  password: string
  confirmPassword: string
}

interface FieldError {
  fullName?: string
  email?: string
  phone?: string
  password?: string
  confirmPassword?: string
}

interface PasswordValidation {
  minLength: boolean
  uppercase: boolean
  lowercase: boolean
  digit: boolean
}

function validateForm(form: FormState): FieldError {
  const errors: FieldError = {}
  if (!form.fullName.trim()) errors.fullName = 'Full name is required'
  if (!form.email.trim()) errors.email = 'Email is required'
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errors.email = 'Invalid email address'
  if (form.phone && !/^\+?[\d\s\-()]{7,15}$/.test(form.phone)) errors.phone = 'Invalid phone number'
  if (!form.password) errors.password = 'Password is required'
  else if (form.password.length < 12) errors.password = 'Password must be at least 12 characters'
  else if (!getPasswordValidation(form.password).uppercase) errors.password = 'Password must contain at least one uppercase letter'
  else if (!getPasswordValidation(form.password).lowercase) errors.password = 'Password must contain at least one lowercase letter'
  else if (!getPasswordValidation(form.password).digit) errors.password = 'Password must contain at least one digit'
  if (!form.confirmPassword) errors.confirmPassword = 'Please confirm your password'
  else if (form.password !== form.confirmPassword) errors.confirmPassword = 'Passwords do not match'
  return errors
}

function getPasswordValidation(password: string): PasswordValidation {
  return {
    minLength: password.length >= 12,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    digit: /\d/.test(password),
  }
}

export default function SignupPage() {
  const router = useRouter()
  const [form, setForm] = useState<FormState>({
    fullName: '',
    email: '',
    phone: '',
    password: '',
    confirmPassword: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<FieldError>({})
  const [loading, setLoading] = useState(false)
  const [serverError, setServerError] = useState('')
  const [passwordValidation, setPasswordValidation] = useState<PasswordValidation>({
    minLength: false,
    uppercase: false,
    lowercase: false,
    digit: false,
  })

  const update = (field: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setForm((prev) => ({ ...prev, [field]: value }))
    if (fieldErrors[field]) setFieldErrors((prev) => ({ ...prev, [field]: undefined }))
    if (field === 'password') {
      setPasswordValidation(getPasswordValidation(value))
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const errors = validateForm(form)
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }

    setLoading(true)
    setServerError('')

    try {
      await register({
        full_name: form.fullName,
        email: form.email,
        phone: form.phone || null,
        password: form.password,
      })
      router.push('/onboarding')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setServerError(axiosErr.response?.data?.detail ?? 'Registration failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600 mb-4">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-xl font-bold text-gray-900 tracking-wider uppercase">BomiPay</h1>
          <p className="text-xs text-gray-500 mt-1">Operations Intelligence</p>
        </div>

        {/* Card */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Create Account</h2>

          {serverError && (
            <div className="mb-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {serverError}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {/* Full Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Full Name</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={form.fullName}
                  onChange={update('fullName')}
                  placeholder="Ada Okonkwo"
                  className={`w-full border rounded-lg px-9 py-2.5 text-sm text-gray-900 bg-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${fieldErrors.fullName ? 'border-red-300' : 'border-gray-300'}`}
                />
              </div>
              {fieldErrors.fullName && <p className="mt-1 text-xs text-red-600">{fieldErrors.fullName}</p>}
            </div>

            {/* Email */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="email"
                  value={form.email}
                  onChange={update('email')}
                  placeholder="ops@merchant.com"
                  className={`w-full border rounded-lg px-9 py-2.5 text-sm text-gray-900 bg-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${fieldErrors.email ? 'border-red-300' : 'border-gray-300'}`}
                />
              </div>
              {fieldErrors.email && <p className="mt-1 text-xs text-red-600">{fieldErrors.email}</p>}
            </div>

            {/* Phone (optional) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Phone <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="tel"
                  value={form.phone}
                  onChange={update('phone')}
                  placeholder="+234 800 000 0000"
                  className={`w-full border rounded-lg px-9 py-2.5 text-sm text-gray-900 bg-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${fieldErrors.phone ? 'border-red-300' : 'border-gray-300'}`}
                />
              </div>
              {fieldErrors.phone && <p className="mt-1 text-xs text-red-600">{fieldErrors.phone}</p>}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={form.password}
                  onChange={update('password')}
                  placeholder="Min. 12 characters"
                  className={`w-full border rounded-lg px-9 py-2.5 text-sm text-gray-900 bg-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${fieldErrors.password ? 'border-red-300' : 'border-gray-300'}`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {fieldErrors.password && <p className="mt-1 text-xs text-red-600">{fieldErrors.password}</p>}
              {form.password && (
                <div className="mt-2 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <div className={`w-4 h-4 rounded-full ${passwordValidation.minLength ? 'bg-green-500' : 'bg-gray-300'}`} />
                    <span className={`text-xs ${passwordValidation.minLength ? 'text-green-600' : 'text-gray-600'}`}>
                      At least 12 characters
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`w-4 h-4 rounded-full ${passwordValidation.uppercase ? 'bg-green-500' : 'bg-gray-300'}`} />
                    <span className={`text-xs ${passwordValidation.uppercase ? 'text-green-600' : 'text-gray-600'}`}>
                      At least one uppercase letter
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`w-4 h-4 rounded-full ${passwordValidation.lowercase ? 'bg-green-500' : 'bg-gray-300'}`} />
                    <span className={`text-xs ${passwordValidation.lowercase ? 'text-green-600' : 'text-gray-600'}`}>
                      At least one lowercase letter
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`w-4 h-4 rounded-full ${passwordValidation.digit ? 'bg-green-500' : 'bg-gray-300'}`} />
                    <span className={`text-xs ${passwordValidation.digit ? 'text-green-600' : 'text-gray-600'}`}>
                      At least one digit
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Confirm Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type={showConfirm ? 'text' : 'password'}
                  value={form.confirmPassword}
                  onChange={update('confirmPassword')}
                  placeholder="Re-enter your password"
                  className={`w-full border rounded-lg px-9 py-2.5 text-sm text-gray-900 bg-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${fieldErrors.confirmPassword ? 'border-red-300' : 'border-gray-300'}`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {fieldErrors.confirmPassword && <p className="mt-1 text-xs text-red-600">{fieldErrors.confirmPassword}</p>}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {loading ? 'Creating account…' : 'Create Account'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Already have an account?{' '}
            <a href="/login" className="text-blue-600 hover:text-blue-700 font-medium">Sign in</a>
          </p>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          BomiPay OpsIntel v1.0 · Internal Use Only
        </p>
      </div>
    </div>
  )
}
