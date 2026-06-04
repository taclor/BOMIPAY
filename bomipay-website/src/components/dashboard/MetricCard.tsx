'use client'

import { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import Sparkline from '@/components/shared/Sparkline'

interface MetricCardProps {
  title: string
  value: string
  subtitle?: string
  badge?: ReactNode
  trend?: { value: number; timestamp: string }[]
  trendColor?: string
  status?: 'critical' | 'warning' | 'ok' | 'info'
  icon?: ReactNode
  className?: string
}

const STATUS_COLORS = {
  critical: 'border-red-600/40 bg-red-500/5',
  warning: 'border-yellow-600/40 bg-yellow-500/5',
  ok: 'border-green-600/40 bg-green-500/5',
  info: 'border-[#1f2937]',
}

export default function MetricCard({
  title,
  value,
  subtitle,
  badge,
  trend,
  trendColor,
  status = 'info',
  icon,
  className,
}: MetricCardProps) {
  return (
    <div className={cn('bg-[#111827] border rounded p-4 flex flex-col gap-3', STATUS_COLORS[status], className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon && <span className="text-gray-500">{icon}</span>}
          <span className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">{title}</span>
        </div>
        {badge}
      </div>

      <div>
        <p className="text-2xl font-mono font-bold text-white leading-none">{value}</p>
        {subtitle && <p className="text-[11px] text-gray-500 mt-1 font-mono">{subtitle}</p>}
      </div>

      {trend && trend.length > 0 && (
        <div className="-mx-1">
          <Sparkline data={trend} color={trendColor ?? '#3b82f6'} height={36} />
        </div>
      )}
    </div>
  )
}
