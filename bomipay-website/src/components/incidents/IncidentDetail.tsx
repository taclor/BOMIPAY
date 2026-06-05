'use client'

import { X, Brain, CheckCircle, Clock } from 'lucide-react'
import SeverityBadge from '@/components/shared/SeverityBadge'
import StatusBadge from '@/components/shared/StatusBadge'
import AmountDisplay from '@/components/shared/AmountDisplay'
import { formatRelative } from '@/lib/utils'
import type { Incident } from '@/types/api'

interface IncidentDetailProps {
  incident: Incident
  onClose: () => void
  onAcknowledge: (id: string) => void
  onResolve: (id: string) => void
  isAcknowledging?: boolean
  isResolving?: boolean
}

export default function IncidentDetail({
  incident,
  onClose,
  onAcknowledge,
  onResolve,
  isAcknowledging,
  isResolving,
}: IncidentDetailProps) {
  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between px-4 py-3 border-b border-[#1f2937]">
        <div className="flex-1 min-w-0 pr-3">
          <div className="flex items-center gap-2 mb-1">
            <SeverityBadge severity={incident.severity} />
            <StatusBadge status={incident.status} />
            <span className="text-[10px] text-gray-500 font-mono">{incident.id}</span>
          </div>
          <h2 className="text-sm font-semibold text-white leading-tight">{incident.title}</h2>
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors flex-shrink-0">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* Description */}
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Description</p>
          <p className="text-xs text-gray-300 leading-relaxed">{incident.description}</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-[#0a0e1a] rounded p-3">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Money at Risk</p>
            <AmountDisplay amount={incident.money_at_risk} size="lg" className="text-red-400 mt-0.5" />
          </div>
          <div className="bg-[#0a0e1a] rounded p-3">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Transactions</p>
            <p className="text-lg font-mono font-bold text-white mt-0.5">{incident.affected_transactions_count}</p>
          </div>
          {incident.affected_provider && (
            <div className="bg-[#0a0e1a] rounded p-3">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Provider</p>
              <p className="text-sm font-mono text-white capitalize mt-0.5">{incident.affected_provider}</p>
            </div>
          )}
          <div className="bg-[#0a0e1a] rounded p-3">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Opened</p>
            <p className="text-xs font-mono text-gray-300 mt-0.5">{formatRelative(incident.created_at)}</p>
          </div>
        </div>

        {/* AI Summary */}
        {incident.ai_summary && (
          <div className="bg-purple-500/5 border border-purple-500/20 rounded p-3">
            <p className="text-[10px] text-purple-400 uppercase tracking-wider mb-1.5 flex items-center gap-1">
              <Brain className="w-3 h-3" /> AI Analysis
            </p>
            <p className="text-xs text-gray-300 leading-relaxed">{incident.ai_summary}</p>
          </div>
        )}

        {/* Timeline */}
        {incident.timeline && incident.timeline.length > 0 && (
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1">
              <Clock className="w-3 h-3" /> Timeline
            </p>
            <div className="space-y-2">
              {incident.timeline.map((entry) => (
                <div key={entry.id} className="flex gap-2 text-xs">
                  <div className="w-1 bg-[#1f2937] rounded-full flex-shrink-0" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-300">{entry.action}</span>
                      <span className="text-[10px] text-gray-600 font-mono">{formatRelative(entry.timestamp)}</span>
                    </div>
                    {entry.actor && <span className="text-[10px] text-gray-500">by {entry.actor}</span>}
                    {entry.notes && <p className="text-[10px] text-gray-400 mt-0.5">{entry.notes}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      {(incident.status === 'open' || incident.status === 'acknowledged') && (
        <div className="px-4 py-3 border-t border-[#1f2937] flex gap-2">
          {incident.status === 'open' && (
            <button
              onClick={() => onAcknowledge(incident.id)}
              disabled={isAcknowledging}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded bg-yellow-600/20 border border-yellow-600/40 text-yellow-400 text-xs hover:bg-yellow-600/30 disabled:opacity-50 transition-colors"
            >
              <CheckCircle className="w-3.5 h-3.5" />
              {isAcknowledging ? 'Acknowledging…' : 'Acknowledge'}
            </button>
          )}
          <button
            onClick={() => onResolve(incident.id)}
            disabled={isResolving}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded bg-green-600/20 border border-green-600/40 text-green-400 text-xs hover:bg-green-600/30 disabled:opacity-50 transition-colors"
          >
            <CheckCircle className="w-3.5 h-3.5" />
            {isResolving ? 'Resolving…' : 'Resolve'}
          </button>
        </div>
      )}
    </div>
  )
}
