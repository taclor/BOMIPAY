'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { formatRelative, formatNGN } from '@/lib/utils'
import type { TimelineEvent } from '@/types/api'

const EVENT_CONFIG: Record<string, { icon: string; color: string; label: string }> = {
  transaction_created: { icon: '💳', color: 'border-blue-500/40', label: 'Transaction Created' },
  webhook_received: { icon: '🔔', color: 'border-yellow-500/40', label: 'Webhook Received' },
  status_changed: { icon: '🔄', color: 'border-orange-500/40', label: 'Status Changed' },
  settlement_received: { icon: '💰', color: 'border-green-500/40', label: 'Settlement Received' },
  dispute_opened: { icon: '⚠️', color: 'border-red-500/40', label: 'Dispute Opened' },
  incident_created: { icon: '🚨', color: 'border-red-600/60', label: 'Incident Created' },
  bank_statement_matched: { icon: '🏦', color: 'border-teal-500/40', label: 'Bank Statement Matched' },
}

interface TimelineEventCardProps {
  event: TimelineEvent
}

export default function TimelineEventCard({ event }: TimelineEventCardProps) {
  const [expanded, setExpanded] = useState(false)
  const config = EVENT_CONFIG[event.event_type] ?? { icon: '•', color: 'border-gray-500/40', label: event.event_type }

  return (
    <div
      className={`bg-[#111827] border-l-2 ${config.color} border border-[#1f2937] rounded p-3 cursor-pointer hover:bg-[#1a2332] transition-colors`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <span className="text-base leading-none flex-shrink-0">{config.icon}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">{config.label}</span>
              {event.transaction_id && (
                <span className="text-[10px] text-blue-400 font-mono">{event.transaction_id}</span>
              )}
              {event.provider && (
                <span className="text-[10px] text-gray-500 font-mono capitalize">{event.provider}</span>
              )}
            </div>
            <p className="text-xs text-gray-300 mt-0.5 leading-tight">{event.description}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {event.amount && (
            <span className="text-[11px] text-green-400 font-mono">{formatNGN(event.amount)}</span>
          )}
          <span className="text-[10px] text-gray-600 font-mono">{formatRelative(event.timestamp)}</span>
          {expanded ? <ChevronDown className="w-3 h-3 text-gray-500" /> : <ChevronRight className="w-3 h-3 text-gray-500" />}
        </div>
      </div>

      {expanded && event.metadata && (
        <div className="mt-3 pt-3 border-t border-[#1f2937]">
          <pre className="text-[10px] text-gray-400 font-mono overflow-auto max-h-40 bg-[#0a0e1a] rounded p-2">
            {JSON.stringify(event.metadata, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
