'use client'

import Shell from '@/components/layout/Shell'
import { useProviderHealthMetrics, useProviderHealthHistory } from '@/hooks/useProviderHealth'
import StatusBadge from '@/components/shared/StatusBadge'
import { bpsToPercent } from '@/lib/utils'
import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import type { ProviderHealthHistory } from '@/types/api'

function HistoryChart({ history }: { history: ProviderHealthHistory }) {
  const chartData = history.history.map((h) => ({
    date: h.date.slice(5),
    reliability: h.reliability_bps / 100,
    latency: h.latency_ms,
  }))

  return (
    <div className="space-y-3">
      <div>
        <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">30-Day Reliability</p>
        <ResponsiveContainer width="100%" height={60}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="relGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" hide />
            <Area type="monotone" dataKey="reliability" stroke="#10b981" fill="url(#relGrad)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Tooltip
              contentStyle={{ background: '#111827', border: '1px solid #1f2937', fontSize: 10, borderRadius: 4 }}
              labelStyle={{ color: '#6b7280' }}
              itemStyle={{ color: '#10b981' }}
              formatter={(v) => [`${Number(v).toFixed(2)}%`, 'Reliability']}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function ProviderCard({ name }: { name: string }) {
  const { data: metrics } = useProviderHealthMetrics()
  const { data: history } = useProviderHealthHistory(name)
  const provider = metrics?.find((m) => m.name === name)

  if (!provider) return null

  const statusColors: Record<string, string> = {
    healthy: 'border-green-600/30',
    degraded: 'border-yellow-600/30',
    down: 'border-red-600/30',
    unknown: 'border-[#1f2937]',
  }

  return (
    <div className={`bg-[#111827] border rounded p-5 space-y-4 ${statusColors[provider.status] ?? 'border-[#1f2937]'}`}>
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-white">{provider.display_name}</h3>
        <StatusBadge status={provider.status} />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Reliability</p>
          <p className="text-xl font-mono font-bold text-white mt-0.5">{bpsToPercent(provider.reliability_bps)}</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Avg Latency</p>
          <p className="text-xl font-mono font-bold text-white mt-0.5">{provider.avg_latency_ms}ms</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Error Rate</p>
          <p className="text-xl font-mono font-bold text-white mt-0.5">{bpsToPercent(provider.error_rate_bps)}</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 pt-2 border-t border-[#1f2937]">
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">P95 Latency</p>
          <p className="text-sm font-mono text-gray-300">{provider.p95_latency_ms}ms</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">P99 Latency</p>
          <p className="text-sm font-mono text-gray-300">{provider.p99_latency_ms}ms</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Uptime</p>
          <p className="text-sm font-mono text-gray-300">{bpsToPercent(provider.uptime_bps)}</p>
        </div>
      </div>

      {history && <HistoryChart history={history} />}

      {provider.last_incident && (
        <p className="text-[10px] text-gray-600">
          Last incident: {new Date(provider.last_incident).toLocaleDateString('en-NG', { timeZone: 'Africa/Lagos' })}
        </p>
      )}
    </div>
  )
}

export default function ProvidersPage() {
  const { data: metrics, refetch } = useProviderHealthMetrics()
  const providers = metrics?.map((m) => m.name) ?? ['paystack', 'flutterwave', 'monnify']

  return (
    <Shell title="Provider Health Console" onRefresh={() => refetch()}>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {providers.map((name) => (
          <ProviderCard key={name} name={name} />
        ))}
      </div>
    </Shell>
  )
}
