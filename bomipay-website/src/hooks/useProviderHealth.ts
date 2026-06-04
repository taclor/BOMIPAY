import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import type { ProviderHealthMetrics, ProviderHealthHistory } from '@/types/api'

const MOCK_METRICS: ProviderHealthMetrics[] = [
  {
    name: 'paystack',
    display_name: 'Paystack',
    status: 'healthy',
    reliability_bps: 9950,
    avg_latency_ms: 120,
    p95_latency_ms: 280,
    p99_latency_ms: 450,
    error_rate_bps: 50,
    uptime_bps: 9980,
    last_checked: new Date().toISOString(),
  },
  {
    name: 'flutterwave',
    display_name: 'Flutterwave',
    status: 'degraded',
    reliability_bps: 9710,
    avg_latency_ms: 380,
    p95_latency_ms: 820,
    p99_latency_ms: 1400,
    error_rate_bps: 290,
    uptime_bps: 9850,
    last_incident: new Date(Date.now() - 3600000).toISOString(),
    last_checked: new Date().toISOString(),
  },
  {
    name: 'monnify',
    display_name: 'Monnify',
    status: 'healthy',
    reliability_bps: 9880,
    avg_latency_ms: 145,
    p95_latency_ms: 310,
    p99_latency_ms: 520,
    error_rate_bps: 120,
    uptime_bps: 9960,
    last_checked: new Date().toISOString(),
  },
]

function generateHistory(baseReliability: number): ProviderHealthHistory['history'] {
  return Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 86400000).toISOString().split('T')[0],
    reliability_bps: Math.floor(baseReliability + (Math.random() - 0.5) * 200),
    latency_ms: Math.floor(150 + Math.random() * 100),
    error_count: Math.floor(Math.random() * 5),
    outage_minutes: Math.random() > 0.9 ? Math.floor(Math.random() * 30) : 0,
  }))
}

const MOCK_HISTORY: Record<string, ProviderHealthHistory> = {
  paystack: { provider: 'paystack', history: generateHistory(9950) },
  flutterwave: { provider: 'flutterwave', history: generateHistory(9710) },
  monnify: { provider: 'monnify', history: generateHistory(9880) },
}

export function useProviderHealthMetrics() {
  return useQuery({
    queryKey: ['providers', 'health-metrics'],
    queryFn: async () => {
      const { data } = await api.get<ProviderHealthMetrics[]>('/providers/health-metrics')
      return data
    },
    placeholderData: MOCK_METRICS,
    staleTime: 30000,
  })
}

export function useProviderHealthHistory(name: string) {
  return useQuery({
    queryKey: ['providers', name, 'history'],
    queryFn: async () => {
      const { data } = await api.get<ProviderHealthHistory>(`/providers/${name}/health-history`)
      return data
    },
    placeholderData: MOCK_HISTORY[name] ?? MOCK_HISTORY['paystack'],
    enabled: !!name,
    staleTime: 300000,
  })
}
