'use client'

import Shell from '@/components/layout/Shell'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { Search, FileUp, Link, CheckCircle, Scale, RefreshCw, CheckSquare } from 'lucide-react'
import type { ActionCenterResponse, ActionItem, ActionType } from '@/types/api'

const MOCK_ACTIONS: ActionCenterResponse = {
  actions: [
    { id: 'a1', action_type: 'investigate_failed_payment', priority: 1, title: 'Investigate failed payments on Flutterwave', description: '23 payments failed in the last 2 hours due to gateway errors', reference_id: 'INC-001', reference_type: 'incident', completed: false, created_at: new Date(Date.now() - 3600000).toISOString() },
    { id: 'a2', action_type: 'upload_bank_statement', priority: 2, title: 'Upload January bank statement', description: 'Bank statement for January 15-21 has not been uploaded', completed: false, created_at: new Date(Date.now() - 86400000).toISOString() },
    { id: 'a3', action_type: 'resolve_unmatched_settlement', priority: 3, title: 'Resolve unmatched settlement', description: 'TXN-00762 settlement amount differs by ₦1,800 from bank record', reference_id: 'TXN-00762', reference_type: 'transaction', completed: false, created_at: new Date(Date.now() - 172800000).toISOString() },
    { id: 'a4', action_type: 'acknowledge_incident', priority: 4, title: 'Acknowledge webhook failure incident', description: 'INC-003: Monnify webhook delivery failure needs acknowledgment', reference_id: 'INC-003', reference_type: 'incident', completed: false, created_at: new Date(Date.now() - 21600000).toISOString() },
    { id: 'a5', action_type: 'check_provider_sync_failure', priority: 5, title: 'Check Flutterwave sync status', description: 'Last successful sync was 3 hours ago, current sync appears stuck', reference_id: 'flutterwave', reference_type: 'provider', completed: false, created_at: new Date(Date.now() - 10800000).toISOString() },
    { id: 'a6', action_type: 'open_dispute', priority: 6, title: 'File dispute for unauthorized charge', description: 'Customer reported unauthorized transaction TXN-00834 for ₦45,000', reference_id: 'TXN-00834', reference_type: 'transaction', completed: true, created_at: new Date(Date.now() - 259200000).toISOString() },
  ],
  total: 6,
  completed: 1,
  pending: 5,
}

const ACTION_ICONS: Record<ActionType, React.ReactNode> = {
  investigate_failed_payment: <Search className="w-4 h-4" />,
  upload_bank_statement: <FileUp className="w-4 h-4" />,
  resolve_unmatched_settlement: <Link className="w-4 h-4" />,
  acknowledge_incident: <CheckCircle className="w-4 h-4" />,
  open_dispute: <Scale className="w-4 h-4" />,
  check_provider_sync_failure: <RefreshCw className="w-4 h-4" />,
}

const ACTION_COLORS: Record<ActionType, string> = {
  investigate_failed_payment: 'text-red-400 bg-red-500/10 border-red-500/30',
  upload_bank_statement: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  resolve_unmatched_settlement: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  acknowledge_incident: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  open_dispute: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
  check_provider_sync_failure: 'text-teal-400 bg-teal-500/10 border-teal-500/30',
}

function ActionCard({ action }: { action: ActionItem }) {
  const colors = ACTION_COLORS[action.action_type] ?? 'text-gray-400 bg-gray-500/10 border-gray-500/30'

  return (
    <div className={`bg-[#111827] border border-[#1f2937] rounded p-4 flex gap-4 ${action.completed ? 'opacity-50' : ''}`}>
      <div className={`w-8 h-8 rounded border flex items-center justify-center flex-shrink-0 ${colors}`}>
        {ACTION_ICONS[action.action_type]}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <p className={`text-sm font-medium ${action.completed ? 'line-through text-gray-500' : 'text-white'}`}>
            {action.title}
          </p>
          <span className="text-[10px] text-gray-600 font-mono flex-shrink-0">P{action.priority}</span>
        </div>
        <p className="text-[11px] text-gray-500 mt-0.5 leading-relaxed">{action.description}</p>
        {action.reference_id && (
          <div className="flex items-center gap-1.5 mt-2">
            <span className="text-[10px] text-gray-600 uppercase">{action.reference_type}:</span>
            <span className="text-[10px] text-blue-400 font-mono">{action.reference_id}</span>
          </div>
        )}
      </div>
      {!action.completed && (
        <button className="flex-shrink-0 px-3 py-1.5 rounded bg-blue-600/20 border border-blue-600/40 text-blue-400 text-xs hover:bg-blue-600/30 transition-colors self-start">
          Take Action
        </button>
      )}
      {action.completed && <CheckSquare className="w-4 h-4 text-green-500 flex-shrink-0 self-start mt-0.5" />}
    </div>
  )
}

export default function ActionsPage() {
  const { data, refetch } = useQuery({
    queryKey: ['action-center'],
    queryFn: async () => {
      const { data } = await api.get<ActionCenterResponse>('/action-center')
      return data
    },
    placeholderData: MOCK_ACTIONS,
    staleTime: 30000,
  })

  const actions = data?.actions.sort((a, b) => a.priority - b.priority) ?? []

  return (
    <Shell title="Action Center" onRefresh={() => refetch()}>
      {/* Progress */}
      <div className="bg-[#111827] border border-[#1f2937] rounded p-4 mb-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">Progress</span>
          <span className="text-xs text-gray-400 font-mono">{data?.completed ?? 0} / {data?.total ?? 0} completed</span>
        </div>
        <div className="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 rounded-full transition-all"
            style={{ width: `${data?.total ? (data.completed / data.total) * 100 : 0}%` }}
          />
        </div>
        <div className="flex gap-4 mt-2 text-[10px]">
          <span className="text-red-400">{data?.pending ?? 0} pending</span>
          <span className="text-green-400">{data?.completed ?? 0} done</span>
        </div>
      </div>

      {/* Action List */}
      <div className="space-y-3">
        {actions.map((action) => <ActionCard key={action.id} action={action} />)}
      </div>
    </Shell>
  )
}
