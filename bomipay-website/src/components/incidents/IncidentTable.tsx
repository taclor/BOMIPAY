'use client'

import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import SeverityBadge from '@/components/shared/SeverityBadge'
import StatusBadge from '@/components/shared/StatusBadge'
import AmountDisplay from '@/components/shared/AmountDisplay'
import { formatRelative } from '@/lib/utils'
import type { Incident } from '@/types/api'

interface IncidentTableProps {
  incidents: Incident[]
  onSelect: (incident: Incident) => void
  selectedId?: string
}

export default function IncidentTable({ incidents, onSelect, selectedId }: IncidentTableProps) {
  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded overflow-hidden">
      <div className="grid grid-cols-[auto_1fr_auto_auto_auto_auto] gap-0 text-[10px] text-gray-500 uppercase tracking-wider px-4 py-2 border-b border-[#1f2937] font-medium">
        <span className="w-20">Severity</span>
        <span className="pl-3">Title</span>
        <span className="w-24 text-center">Status</span>
        <span className="w-20 text-center">Provider</span>
        <span className="w-24 text-right">At Risk</span>
        <span className="w-20 text-right">Age</span>
      </div>

      {incidents.map((incident) => (
        <div
          key={incident.id}
          onClick={() => onSelect(incident)}
          className={`grid grid-cols-[auto_1fr_auto_auto_auto_auto] gap-0 items-center px-4 py-3 border-b border-[#1f2937] last:border-0 cursor-pointer transition-colors hover:bg-[#1a2332] ${selectedId === incident.id ? 'bg-blue-900/20 border-l-2 border-l-blue-500' : ''}`}
        >
          <span className="w-20"><SeverityBadge severity={incident.severity} /></span>
          <div className="pl-3 min-w-0">
            <p className="text-xs text-white font-medium truncate">{incident.title}</p>
            <p className="text-[10px] text-gray-500 font-mono mt-0.5">{incident.id}</p>
          </div>
          <span className="w-24 flex justify-center"><StatusBadge status={incident.status} /></span>
          <span className="w-20 text-center text-[11px] text-gray-400 font-mono capitalize">{incident.affected_provider ?? '—'}</span>
          <span className="w-24 text-right"><AmountDisplay amount={incident.money_at_risk} size="sm" /></span>
          <span className="w-20 text-right text-[10px] text-gray-500 font-mono">{formatRelative(incident.created_at)}</span>
        </div>
      ))}
    </div>
  )
}
