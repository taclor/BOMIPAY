'use client'

import Shell from '@/components/layout/Shell'
import MetricCard from '@/components/dashboard/MetricCard'
import ProviderHealthCard from '@/components/dashboard/ProviderHealthCard'
import ActivityFeed from '@/components/dashboard/ActivityFeed'
import AIInsightPanel from '@/components/dashboard/AIInsightPanel'
import {
  useDashboardSummary,
  useDashboardMetrics,
  useDashboardProviders,
  useDashboardActivities,
  useAISummary,
} from '@/hooks/useDashboard'
import { bpsToPercent, formatNGN } from '@/lib/utils'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, TrendingDown, ShieldAlert, Clock, AlertCircle } from 'lucide-react'

function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3 mb-6">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div key={i} className="bg-white rounded-lg border border-gray-200 p-6 animate-pulse">
          <div className="h-4 bg-gray-200 rounded mb-2 w-1/2" />
          <div className="h-8 bg-gray-200 rounded w-1/3" />
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const qc = useQueryClient()
  const { data: summary, isLoading } = useDashboardSummary()
  const { data: metrics } = useDashboardMetrics()
  const { data: providers } = useDashboardProviders()
  const { data: activities } = useDashboardActivities()
  const { data: aiSummary } = useAISummary()

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['dashboard'] })
    qc.invalidateQueries({ queryKey: ['ai', 'summary'] })
  }

  if (isLoading) {
    return (
      <Shell title="Mission Control" subtitle="LOADING">
        <DashboardSkeleton />
      </Shell>
    )
  }

  return (
    <Shell title="Mission Control" subtitle="LIVE" onRefresh={refresh}>
      {/* KPI Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3 mb-6">
        <MetricCard
          title="Success Rate"
          value={summary ? bpsToPercent(summary.payment_success_rate) : '—'}
          subtitle={`${summary?.total_transactions_24h.toLocaleString() ?? '—'} txns / 24h`}
          trend={metrics?.success_rate_trend}
          trendColor="#10b981"
          status="ok"
          icon={<AlertCircle className="w-3.5 h-3.5" />}
        />
        <MetricCard
          title="Failed Transactions"
          value={summary?.failed_transactions_count.toString() ?? '—'}
          subtitle="Last 24 hours"
          trend={metrics?.failed_trend}
          trendColor="#ef4444"
          status={summary && summary.failed_transactions_count > 50 ? 'critical' : summary && summary.failed_transactions_count > 20 ? 'warning' : 'ok'}
          icon={<TrendingDown className="w-3.5 h-3.5" />}
        />
        <MetricCard
          title="Money at Risk"
          value={summary ? formatNGN(summary.money_at_risk_amount) : '—'}
          status={summary?.money_at_risk_status ?? 'info'}
          icon={<ShieldAlert className="w-3.5 h-3.5" />}
          badge={summary ? (
            <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase tracking-wider ${
              summary.money_at_risk_status === 'critical' ? 'bg-red-50 text-red-700 border-red-200' :
              summary.money_at_risk_status === 'warning' ? 'bg-yellow-50 text-yellow-700 border-yellow-200' :
              'bg-green-50 text-green-700 border-green-200'
            }`}>{summary.money_at_risk_status}</span>
          ) : undefined}
        />
        <MetricCard
          title="Pending Settlements"
          value={summary?.pending_settlements_count.toString() ?? '—'}
          subtitle={summary ? formatNGN(summary.pending_settlements_amount) : '—'}
          status="info"
          icon={<Clock className="w-3.5 h-3.5" />}
        />
        <MetricCard
          title="Open Incidents"
          value={summary?.open_incidents_count.toString() ?? '—'}
          status={summary && summary.open_incidents_count > 5 ? 'critical' : summary && summary.open_incidents_count > 0 ? 'warning' : 'ok'}
          icon={<AlertTriangle className="w-3.5 h-3.5" />}
        />
      </div>

      {/* Provider Health */}
      <div className="mb-6">
        <h2 className="text-[10px] text-gray-500 uppercase tracking-wider mb-3 font-medium">Provider Health</h2>
        {(providers ?? []).length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-lg p-8 flex flex-col items-center justify-center text-center">
            <p className="text-2xl mb-2">🔗</p>
            <p className="text-gray-900 font-medium mb-1">No providers connected</p>
            <p className="text-gray-600 text-sm mb-4">
              Start by connecting a payment provider to sync transactions and track settlement data.
            </p>
            <a
              href="/providers/connect"
              className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors"
            >
              Connect Your First Provider
            </a>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {(providers ?? []).map((provider) => (
              <ProviderHealthCard key={provider.name} provider={provider} />
            ))}
          </div>
        )}
      </div>

      {/* Activity + AI */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3">Recent Activity</h2>
          {(activities ?? []).length === 0 ? (
            <div className="text-center py-8 text-gray-500 text-sm">
              <p>No data yet. Connect a payment provider to get started.</p>
            </div>
          ) : (
            <ActivityFeed activities={activities ?? []} />
          )}
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h2 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
            AI Operational Insight
          </h2>
          {aiSummary && <AIInsightPanel summary={aiSummary} />}
        </div>
      </div>
    </Shell>
  )
}
