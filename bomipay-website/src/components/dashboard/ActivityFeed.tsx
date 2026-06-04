'use client'

import { formatRelative } from '@/lib/utils'
import type { Activity } from '@/types/api'

const ACTIVITY_COLORS: Record<string, string> = {
  incident_created: 'bg-red-500',
  transaction_created: 'bg-blue-500',
  settlement_received: 'bg-green-500',
  dispute_opened: 'bg-orange-500',
  webhook_received: 'bg-yellow-500',
  bank_statement_matched: 'bg-teal-500',
  status_changed: 'bg-purple-500',
}

interface ActivityFeedProps {
  activities: Activity[]
}

export default function ActivityFeed({ activities }: ActivityFeedProps) {
  return (
    <div className="space-y-0">
      {activities.map((activity, index) => (
        <div key={activity.id} className="flex gap-3 py-2.5 border-b border-[#1f2937] last:border-0">
          <div className="flex flex-col items-center pt-1">
            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${ACTIVITY_COLORS[activity.type] ?? 'bg-gray-500'}`} />
            {index < activities.length - 1 && <div className="w-px flex-1 bg-[#1f2937] mt-1" />}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs text-white font-medium leading-tight">{activity.title}</p>
            <p className="text-[11px] text-gray-500 mt-0.5 leading-tight">{activity.description}</p>
          </div>
          <span className="text-[10px] text-gray-600 font-mono flex-shrink-0 pt-0.5">
            {formatRelative(activity.timestamp)}
          </span>
        </div>
      ))}
    </div>
  )
}
