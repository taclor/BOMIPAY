'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Target,
  Clock,
  AlertTriangle,
  DollarSign,
  CheckSquare,
  Building2,
  GitBranch,
  Bot,
  Activity,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { href: '/dashboard', label: 'Mission Control', icon: Target },
  { href: '/timeline', label: 'Timeline', icon: Clock },
  { href: '/incidents', label: 'Incident Center', icon: AlertTriangle },
  { href: '/reconciliation', label: 'Reconciliation', icon: DollarSign },
  { href: '/actions', label: 'Action Center', icon: CheckSquare },
  { href: '/providers', label: 'Providers', icon: Building2 },
  { href: '/graph', label: 'Payment Graph', icon: GitBranch },
  { href: '/ai', label: 'AI Assistant', icon: Bot },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-56 min-h-screen bg-[#111827] border-r border-[#1f2937] flex flex-col">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-[#1f2937]">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-500" />
          <span className="font-bold text-white text-sm tracking-wider uppercase">BomiPay</span>
        </div>
        <p className="text-[10px] text-gray-500 mt-0.5 tracking-widest uppercase">Ops Intelligence</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== '/' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded text-xs transition-all',
                active
                  ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-[#1f2937]'
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{label}</span>
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-[#1f2937]">
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
          <span className="text-[10px] text-gray-500">LIVE</span>
        </div>
      </div>
    </aside>
  )
}
