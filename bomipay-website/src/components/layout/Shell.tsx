'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

interface ShellProps {
  title: string
  subtitle?: string
  onRefresh?: () => void
  isRefreshing?: boolean
  children: React.ReactNode
}

export default function Shell({ title, subtitle, onRefresh, isRefreshing, children }: ShellProps) {
  const { isAuthenticated, _hydrated } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    if (_hydrated && !isAuthenticated) {
      router.push('/login')
    }
  }, [_hydrated, isAuthenticated, router])

  if (!_hydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-spin h-8 w-8 border-2 border-blue-600 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar title={title} subtitle={subtitle} onRefresh={onRefresh} isRefreshing={isRefreshing} />
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
