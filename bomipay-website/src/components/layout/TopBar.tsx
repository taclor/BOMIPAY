'use client'

import { Bell, LogOut, User, RefreshCw } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { useRouter } from 'next/navigation'

interface TopBarProps {
  title: string
  subtitle?: string
  onRefresh?: () => void
  isRefreshing?: boolean
}

export default function TopBar({ title, subtitle, onRefresh, isRefreshing }: TopBarProps) {
  const { user, clearAuth } = useAuthStore()
  const router = useRouter()

  const handleLogout = () => {
    clearAuth()
    router.push('/login')
  }

  return (
    <header className="h-12 bg-[#111827] border-b border-[#1f2937] flex items-center justify-between px-6">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-white">{title}</h1>
        {subtitle && <span className="text-xs text-gray-500 font-mono">{subtitle}</span>}
      </div>

      <div className="flex items-center gap-3">
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="p-1.5 rounded hover:bg-[#1f2937] text-gray-400 hover:text-gray-200 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        )}

        <button className="p-1.5 rounded hover:bg-[#1f2937] text-gray-400 hover:text-gray-200 transition-colors relative">
          <Bell className="w-3.5 h-3.5" />
          <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 bg-red-500 rounded-full" />
        </button>

        <div className="flex items-center gap-2 pl-3 border-l border-[#1f2937]">
          <div className="w-6 h-6 rounded bg-blue-600/30 border border-blue-600/50 flex items-center justify-center">
            <User className="w-3 h-3 text-blue-400" />
          </div>
          {user && (
            <span className="text-xs text-gray-300 font-mono">{user.email.split('@')[0]}</span>
          )}
          <button
            onClick={handleLogout}
            className="p-1 rounded hover:bg-[#1f2937] text-gray-500 hover:text-gray-300 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </header>
  )
}
