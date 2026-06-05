import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import type {
  DashboardSummary,
  DashboardMetrics,
  ProviderSummary,
  Activity,
  AISummary,
} from '@/types/api'

const MOCK_SUMMARY: DashboardSummary = {
  payment_success_rate: 9423,
  failed_transactions_count: 47,
  money_at_risk_amount: 3_450_000_00,
  money_at_risk_status: 'warning',
  pending_settlements_count: 12,
  pending_settlements_amount: 8_200_000_00,
  open_incidents_count: 3,
  total_transactions_24h: 1842,
  transaction_volume_24h: 52_300_000_00,
}

const MOCK_METRICS: DashboardMetrics = {
  success_rate_trend: Array.from({ length: 24 }, (_, i) => ({
    timestamp: new Date(Date.now() - (23 - i) * 3600000).toISOString(),
    value: 9200 + Math.random() * 600,
  })),
  failed_trend: Array.from({ length: 24 }, (_, i) => ({
    timestamp: new Date(Date.now() - (23 - i) * 3600000).toISOString(),
    value: Math.floor(Math.random() * 10 + 2),
  })),
  volume_trend: Array.from({ length: 24 }, (_, i) => ({
    timestamp: new Date(Date.now() - (23 - i) * 3600000).toISOString(),
    value: Math.floor(Math.random() * 5_000_000_00 + 1_000_000_00),
  })),
}

const MOCK_PROVIDERS: ProviderSummary[] = [
  { name: 'paystack', status: 'healthy', reliability_bps: 9950, latency_ms: 120, last_checked: new Date().toISOString() },
  { name: 'flutterwave', status: 'degraded', reliability_bps: 9710, latency_ms: 380, last_checked: new Date().toISOString() },
  { name: 'monnify', status: 'healthy', reliability_bps: 9880, latency_ms: 145, last_checked: new Date().toISOString() },
]

const MOCK_ACTIVITIES: Activity[] = [
  { id: '1', type: 'incident_created', title: 'Flutterwave degraded performance', description: 'High error rate detected on FLW gateway', timestamp: new Date(Date.now() - 600000).toISOString(), severity: 'high' },
  { id: '2', type: 'settlement_received', title: 'Settlement received', description: '₦2,400,000 settlement from Paystack', timestamp: new Date(Date.now() - 1200000).toISOString(), severity: 'info' },
  { id: '3', type: 'transaction_created', title: 'High value transaction', description: 'Transaction TXN-00891 for ₦450,000', timestamp: new Date(Date.now() - 1800000).toISOString(), severity: 'info' },
  { id: '4', type: 'dispute_opened', title: 'Dispute opened', description: 'Customer dispute on TXN-00762', timestamp: new Date(Date.now() - 3600000).toISOString(), severity: 'medium' },
  { id: '5', type: 'bank_statement_matched', title: 'Statement matched', description: '15 entries matched automatically', timestamp: new Date(Date.now() - 7200000).toISOString(), severity: 'info' },
]

const MOCK_AI_SUMMARY: AISummary = {
  summary: 'Flutterwave is showing degraded performance with 2.9% error rate. 3 open incidents require immediate attention. ₦34.5M is currently at risk across 47 failed transactions.',
  key_issues: ['Flutterwave error rate elevated at 2.9%', '₦34.5M in unreconciled transactions', '12 pending settlements need review'],
  recommended_actions: ['Acknowledge the Flutterwave incident', 'Review unmatched bank statement entries', 'Investigate TXN-00891 failure pattern'],
  confidence: 87,
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: async () => {
      const { data } = await api.get<DashboardSummary>('/dashboard')
      return data
    },
    staleTime: 30000,
  })
}

export function useDashboardMetrics() {
  return useQuery({
    queryKey: ['dashboard', 'metrics'],
    queryFn: async () => {
      const { data } = await api.get<DashboardMetrics>('/dashboard/metrics')
      return data
    },
    staleTime: 60000,
  })
}

export function useDashboardProviders() {
  return useQuery({
    queryKey: ['dashboard', 'providers'],
    queryFn: async () => {
      const { data } = await api.get<ProviderSummary[]>('/dashboard/providers')
      return data
    },
    staleTime: 30000,
  })
}

export function useDashboardActivities() {
  return useQuery({
    queryKey: ['dashboard', 'activities'],
    queryFn: async () => {
      const { data } = await api.get<Activity[]>('/dashboard/activities')
      return data
    },
    staleTime: 15000,
  })
}

export function useAISummary() {
  return useQuery({
    queryKey: ['ai', 'summary'],
    queryFn: async () => {
      const { data } = await api.get<AISummary>('/ai-assistant/summary')
      return data
    },
    staleTime: 120000,
  })
}
