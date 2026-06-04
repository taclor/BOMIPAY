'use client'

import { bpsToPercent } from '@/lib/utils'
import { cn } from '@/lib/utils'
import Sparkline from '@/components/shared/Sparkline'
import StatusBadge from '@/components/shared/StatusBadge'
import type { ProviderSummary } from '@/types/api'

interface ProviderHealthCardProps {
  provider: ProviderSummary
  history?: { value: number; timestamp: string }[]
}

const PROVIDER_COLORS: Record<string, string> = {
  paystack: '#3b82f6',
  flutterwave: '#f97316',
  monnify: '#14b8a6',
}

export default function ProviderHealthCard({ provider, history }: ProviderHealthCardProps) {
  const color = PROVIDER_COLORS[provider.name] ?? '#6b7280'
  const reliability = bpsToPercent(provider.reliability_bps)

  return (
    <div className={cn(
      'bg-[#111827] border rounded p-4 space-y-3',
      provider.status === 'healthy' ? 'border-[#1f2937]' :
      provider.status === 'degraded' ? 'border-yellow-600/30' :
      'border-red-600/30'
    )}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: color }} />
          <span className="text-sm font-semibold text-white capitalize">{provider.name}</span>
        </div>
        <StatusBadge status={provider.status} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Reliability</p>
          <p className="text-lg font-mono font-bold text-white">{reliability}</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Latency</p>
          <p className="text-lg font-mono font-bold text-white">{provider.latency_ms}ms</p>
        </div>
      </div>

      {history && history.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">24h Trend</p>
          <Sparkline data={history} color={color} height={32} />
        </div>
      )}
    </div>
  )
}
