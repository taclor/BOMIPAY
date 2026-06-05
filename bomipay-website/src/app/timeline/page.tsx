'use client'

import { useState } from 'react'
import Shell from '@/components/layout/Shell'
import TimelineEventCard from '@/components/timeline/TimelineEvent'
import { useTimeline } from '@/hooks/useTimeline'
import type { TimelineEventType } from '@/types/api'
import { Filter } from 'lucide-react'

const EVENT_TYPES: { value: TimelineEventType | ''; label: string }[] = [
  { value: '', label: 'All Events' },
  { value: 'transaction_created', label: '💳 Transactions' },
  { value: 'webhook_received', label: '🔔 Webhooks' },
  { value: 'status_changed', label: '🔄 Status Changes' },
  { value: 'settlement_received', label: '💰 Settlements' },
  { value: 'dispute_opened', label: '⚠️ Disputes' },
  { value: 'incident_created', label: '🚨 Incidents' },
  { value: 'bank_statement_matched', label: '🏦 Bank Matches' },
]

const PROVIDERS = ['', 'paystack', 'flutterwave', 'monnify']

export default function TimelinePage() {
  const [eventType, setEventType] = useState<TimelineEventType | ''>('')
  const [provider, setProvider] = useState('')

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, refetch } = useTimeline({
    event_type: eventType || undefined,
    provider: provider || undefined,
  })

  const allEvents = data?.pages.flatMap((p) => p.events) ?? []

  return (
    <Shell title="Unified Payment Timeline" onRefresh={() => refetch()}>
      {/* Filters */}
      <div className="flex items-center gap-3 mb-5">
        <Filter className="w-3.5 h-3.5 text-gray-500" />
        <select
          value={eventType}
          onChange={(e) => setEventType(e.target.value as TimelineEventType | '')}
          className="bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {EVENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {PROVIDERS.map((p) => (
            <option key={p} value={p}>{p || 'All Providers'}</option>
          ))}
        </select>

        <span className="text-[10px] text-gray-600 font-mono">{allEvents.length} events</span>
      </div>

      {/* Event List */}
      <div className="space-y-2">
        {allEvents.map((event) => (
          <TimelineEventCard key={event.id} event={event} />
        ))}
      </div>

      {hasNextPage && (
        <div className="text-center mt-6">
          <button
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
            className="px-6 py-2 rounded-lg bg-white border border-gray-200 text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            {isFetchingNextPage ? 'Loading…' : 'Load More Events'}
          </button>
        </div>
      )}

      {allEvents.length === 0 && (
        <div className="text-center py-16 text-gray-600">
          <p className="text-sm">No events found</p>
        </div>
      )}
    </Shell>
  )
}
