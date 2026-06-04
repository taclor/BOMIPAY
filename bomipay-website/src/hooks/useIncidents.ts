import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '@/lib/api'
import type { Incident, PaginatedResponse } from '@/types/api'

const MOCK_INCIDENTS: Incident[] = [
  {
    id: 'INC-001',
    title: 'Flutterwave elevated error rate',
    description: 'Flutterwave is returning HTTP 500 errors at an elevated rate of 2.9%. This is affecting payment processing for affected merchants.',
    severity: 'high',
    status: 'open',
    affected_provider: 'flutterwave',
    affected_transactions_count: 23,
    money_at_risk: 1_200_000_00,
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 1800000).toISOString(),
    ai_summary: 'Flutterwave is experiencing intermittent 500 errors, likely due to their infrastructure issues. Pattern matches previous incident INC-089 from 3 weeks ago.',
    timeline: [
      { id: 't1', action: 'Incident created', timestamp: new Date(Date.now() - 3600000).toISOString() },
      { id: 't2', action: 'Alert triggered', timestamp: new Date(Date.now() - 3500000).toISOString(), notes: 'Error rate exceeded 2% threshold' },
    ],
  },
  {
    id: 'INC-002',
    title: 'Settlement reconciliation mismatch',
    description: 'Multiple settlement amounts from Paystack do not match bank statement entries for the period 2024-01-15 to 2024-01-20.',
    severity: 'medium',
    status: 'acknowledged',
    affected_provider: 'paystack',
    affected_transactions_count: 8,
    money_at_risk: 450_000_00,
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 43200000).toISOString(),
    acknowledged_at: new Date(Date.now() - 43200000).toISOString(),
    ai_summary: 'Reconciliation mismatch likely due to fee calculation difference. Paystack applies fees before settlement, but statement shows gross amount.',
    timeline: [
      { id: 't3', action: 'Incident created', timestamp: new Date(Date.now() - 86400000).toISOString() },
      { id: 't4', action: 'Acknowledged', actor: 'admin@example.com', timestamp: new Date(Date.now() - 43200000).toISOString() },
    ],
  },
  {
    id: 'INC-003',
    title: 'Webhook delivery failure - Monnify',
    description: 'Monnify webhooks are not being delivered to the configured endpoint. Last successful delivery was 6 hours ago.',
    severity: 'critical',
    status: 'investigating',
    affected_provider: 'monnify',
    affected_transactions_count: 45,
    money_at_risk: 2_300_000_00,
    created_at: new Date(Date.now() - 21600000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
    ai_summary: 'Webhook endpoint may have an SSL certificate issue. Certificate expires in 2 days. Immediate renewal recommended.',
    timeline: [
      { id: 't5', action: 'Incident created', timestamp: new Date(Date.now() - 21600000).toISOString() },
      { id: 't6', action: 'Investigating', actor: 'ops@example.com', timestamp: new Date(Date.now() - 3600000).toISOString(), notes: 'Checking SSL certificate' },
    ],
  },
]

export function useIncidents() {
  return useQuery({
    queryKey: ['incidents'],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<Incident> | Incident[]>('/incidents')
      return Array.isArray(data) ? data : data.items
    },
    placeholderData: MOCK_INCIDENTS,
    staleTime: 30000,
  })
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: ['incidents', id],
    queryFn: async () => {
      const { data } = await api.get<Incident>(`/incidents/${id}`)
      return data
    },
    placeholderData: MOCK_INCIDENTS.find((i) => i.id === id),
    enabled: !!id,
  })
}

export function useAcknowledgeIncident() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post(`/incidents/${id}/acknowledge`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incidents'] })
    },
  })
}

export function useResolveIncident() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post(`/incidents/${id}/resolve`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incidents'] })
    },
  })
}
