import { useInfiniteQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import type { TimelineResponse, TimelineEventType } from '@/types/api'

interface TimelineFilters {
  status?: string
  provider?: string
  event_type?: TimelineEventType
  start_date?: string
  end_date?: string
}

const MOCK_EVENTS: TimelineResponse = {
  events: [
    { id: 'ev1', event_type: 'transaction_created', transaction_id: 'TXN-00891', amount: 45000000, currency: 'NGN', provider: 'paystack', status: 'pending', description: 'New transaction created', timestamp: new Date(Date.now() - 300000).toISOString() },
    { id: 'ev2', event_type: 'webhook_received', transaction_id: 'TXN-00891', description: 'Webhook received from Paystack: payment.success', timestamp: new Date(Date.now() - 280000).toISOString(), provider: 'paystack' },
    { id: 'ev3', event_type: 'status_changed', transaction_id: 'TXN-00891', status: 'success', description: 'Transaction status changed to success', timestamp: new Date(Date.now() - 260000).toISOString() },
    { id: 'ev4', event_type: 'settlement_received', amount: 2400000000, currency: 'NGN', provider: 'paystack', description: 'Settlement batch received', timestamp: new Date(Date.now() - 3600000).toISOString() },
    { id: 'ev5', event_type: 'dispute_opened', transaction_id: 'TXN-00762', amount: 18000000, description: 'Customer opened dispute for unauthorized charge', timestamp: new Date(Date.now() - 7200000).toISOString() },
    { id: 'ev6', event_type: 'incident_created', description: 'Incident INC-001 opened: Flutterwave elevated error rate', timestamp: new Date(Date.now() - 10800000).toISOString() },
    { id: 'ev7', event_type: 'bank_statement_matched', description: '15 transactions matched to bank statement entries', timestamp: new Date(Date.now() - 14400000).toISOString() },
    { id: 'ev8', event_type: 'transaction_created', transaction_id: 'TXN-00890', amount: 12000000, currency: 'NGN', provider: 'flutterwave', status: 'failed', description: 'Transaction failed - gateway error', timestamp: new Date(Date.now() - 18000000).toISOString() },
  ],
  has_more: false,
}

export function useTimeline(filters: TimelineFilters = {}) {
  return useInfiniteQuery({
    queryKey: ['timeline', filters],
    queryFn: async ({ pageParam }) => {
      const params = new URLSearchParams()
      if (pageParam) params.set('cursor', pageParam as string)
      if (filters.status) params.set('status', filters.status)
      if (filters.provider) params.set('provider', filters.provider)
      if (filters.event_type) params.set('event_type', filters.event_type)
      if (filters.start_date) params.set('start_date', filters.start_date)
      if (filters.end_date) params.set('end_date', filters.end_date)

      const { data } = await api.get<TimelineResponse>(`/timeline/payments?${params}`)
      return data
    },
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? null,
    placeholderData: { pages: [MOCK_EVENTS], pageParams: [null] },
    staleTime: 15000,
  })
}
