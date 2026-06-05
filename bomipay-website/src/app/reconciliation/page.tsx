'use client'

import { useRef } from 'react'
import Shell from '@/components/layout/Shell'
import { useQuery, useMutation } from '@tanstack/react-query'
import api from '@/lib/api'
import StatusBadge from '@/components/shared/StatusBadge'
import AmountDisplay from '@/components/shared/AmountDisplay'
import { formatDate } from '@/lib/utils'
import { Upload, CheckCircle2, XCircle, HelpCircle } from 'lucide-react'
import type { ReconciliationEntry, BankStatementEntry, MatchStatus } from '@/types/api'

const MOCK_RECON: ReconciliationEntry[] = [
  { id: 'r1', provider: 'paystack', transaction_id: 'TXN-00891', provider_amount: 45000000, bank_amount: 45000000, difference: 0, match_status: 'matched', settlement_date: new Date(Date.now() - 86400000).toISOString(), currency: 'NGN' },
  { id: 'r2', provider: 'flutterwave', transaction_id: 'TXN-00762', provider_amount: 18000000, bank_amount: 17820000, difference: 180000, match_status: 'mismatched', settlement_date: new Date(Date.now() - 172800000).toISOString(), currency: 'NGN' },
  { id: 'r3', provider: 'monnify', transaction_id: 'TXN-00821', provider_amount: 30000000, match_status: 'pending', settlement_date: new Date(Date.now() - 259200000).toISOString(), currency: 'NGN' },
  { id: 'r4', provider: 'paystack', transaction_id: 'TXN-00903', provider_amount: 12000000, bank_amount: 12000000, difference: 0, match_status: 'matched', settlement_date: new Date(Date.now() - 86400000).toISOString(), currency: 'NGN' },
]

const MOCK_BANK: BankStatementEntry[] = [
  { id: 'b1', date: new Date(Date.now() - 86400000).toISOString(), description: 'PAYSTACK SETTLEMENT 20240115', amount: 45000000, balance: 1200000000, reference: 'PSK-20240115', match_status: 'matched', matched_transaction_id: 'TXN-00891' },
  { id: 'b2', date: new Date(Date.now() - 172800000).toISOString(), description: 'FLUTTERWAVE LTD', amount: 17820000, balance: 1155000000, match_status: 'mismatched', matched_transaction_id: 'TXN-00762' },
  { id: 'b3', date: new Date(Date.now() - 86400000).toISOString(), description: 'PAYSTACK SETTLEMENT 20240115-2', amount: 12000000, balance: 1143000000, reference: 'PSK-20240115-2', match_status: 'matched', matched_transaction_id: 'TXN-00903' },
  { id: 'b4', date: new Date(Date.now() - 345600000).toISOString(), description: 'INBOUND TRANSFER', amount: 8500000, balance: 1151500000, match_status: 'unmatched' },
]

const MATCH_ICONS: Record<MatchStatus, React.ReactNode> = {
  matched: <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />,
  mismatched: <XCircle className="w-3.5 h-3.5 text-red-500" />,
  pending: <HelpCircle className="w-3.5 h-3.5 text-gray-500" />,
  unmatched: <XCircle className="w-3.5 h-3.5 text-orange-500" />,
}

export default function ReconciliationPage() {
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: recon, refetch: refetchRecon } = useQuery({
    queryKey: ['reconciliation'],
    queryFn: async () => {
      const { data } = await api.get<ReconciliationEntry[]>('/reconciliation')
      return data
    },
    placeholderData: MOCK_RECON,
  })

  const { data: bank, refetch: refetchBank } = useQuery({
    queryKey: ['bank-statements'],
    queryFn: async () => {
      const { data } = await api.get<BankStatementEntry[]>('/bank-statements/entries')
      return data
    },
    placeholderData: MOCK_BANK,
  })

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      await api.post('/bank-statements/import', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    },
    onSuccess: () => { refetchBank(); refetchRecon() },
  })

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) upload.mutate(file)
  }

  return (
    <Shell title="Reconciliation Desk" onRefresh={() => { refetchRecon(); refetchBank() }}>
      <div className="flex items-center justify-between mb-5">
        <div className="flex gap-4 text-[10px] text-gray-500 uppercase tracking-wider">
          <span className="text-green-400">{recon?.filter(r => r.match_status === 'matched').length ?? 0} matched</span>
          <span className="text-red-400">{recon?.filter(r => r.match_status === 'mismatched').length ?? 0} mismatched</span>
          <span className="text-gray-500">{recon?.filter(r => r.match_status === 'pending').length ?? 0} pending</span>
        </div>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={upload.isPending}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          <Upload className="w-3.5 h-3.5" />
          {upload.isPending ? 'Uploading…' : 'Upload Bank Statement'}
        </button>
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" onChange={handleFile} className="hidden" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Provider Settlements */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-200 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Provider Settlements</h3>
            <span className="text-[10px] text-gray-400">{recon?.length ?? 0} entries</span>
          </div>
          <div className="divide-y divide-gray-100">
            {(recon ?? []).map((entry) => (
              <div key={entry.id} className="px-4 py-3 flex items-center gap-3">
                {MATCH_ICONS[entry.match_status]}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-900 font-mono">{entry.transaction_id}</span>
                    <span className="text-[10px] text-gray-500 capitalize">{entry.provider}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <AmountDisplay amount={entry.provider_amount} size="sm" />
                    {entry.difference !== undefined && entry.difference !== 0 && (
                      <span className="text-[10px] text-red-600 font-mono">
                        Δ {entry.difference > 0 ? '+' : ''}{(entry.difference / 100).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>
                <StatusBadge status={entry.match_status} />
              </div>
            ))}
          </div>
        </div>

        {/* Bank Statement */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-200 flex items-center justify-between">
            <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Bank Statement Entries</h3>
            <span className="text-[10px] text-gray-400">{bank?.length ?? 0} entries</span>
          </div>
          <div className="divide-y divide-gray-100">
            {(bank ?? []).map((entry) => (
              <div key={entry.id} className="px-4 py-3 flex items-center gap-3">
                {MATCH_ICONS[entry.match_status]}
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-900 truncate">{entry.description}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <AmountDisplay amount={entry.amount} size="sm" />
                    <span className="text-[10px] text-gray-400 font-mono">{formatDate(entry.date).split(',')[0]}</span>
                  </div>
                </div>
                <StatusBadge status={entry.match_status} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </Shell>
  )
}
