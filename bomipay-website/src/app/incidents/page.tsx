'use client'

import { useState } from 'react'
import Shell from '@/components/layout/Shell'
import IncidentTable from '@/components/incidents/IncidentTable'
import IncidentDetail from '@/components/incidents/IncidentDetail'
import { useIncidents, useAcknowledgeIncident, useResolveIncident } from '@/hooks/useIncidents'
import type { Incident } from '@/types/api'

export default function IncidentsPage() {
  const [selected, setSelected] = useState<Incident | null>(null)
  const { data: incidents, refetch } = useIncidents()
  const acknowledge = useAcknowledgeIncident()
  const resolve = useResolveIncident()

  const handleAcknowledge = (id: string) => {
    acknowledge.mutate(id)
  }

  const handleResolve = (id: string) => {
    resolve.mutate(id, { onSuccess: () => setSelected(null) })
  }

  return (
    <Shell title="Incident Center" onRefresh={() => refetch()}>
      <div className={`flex gap-4 h-full ${selected ? 'flex-row' : 'flex-col'}`}>
        <div className={selected ? 'flex-1 min-w-0 overflow-auto' : 'w-full'}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex gap-3">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">{incidents?.length ?? 0} incidents</span>
              {acknowledge.isPending && <span className="text-[10px] text-yellow-400">Acknowledging…</span>}
              {resolve.isPending && <span className="text-[10px] text-green-400">Resolving…</span>}
            </div>
          </div>
          <IncidentTable
            incidents={incidents ?? []}
            onSelect={setSelected}
            selectedId={selected?.id}
          />
        </div>

        {selected && (
          <div className="w-80 flex-shrink-0 h-[calc(100vh-9rem)]">
            <IncidentDetail
              incident={selected}
              onClose={() => setSelected(null)}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
              isAcknowledging={acknowledge.isPending}
              isResolving={resolve.isPending}
            />
          </div>
        )}
      </div>
    </Shell>
  )
}
