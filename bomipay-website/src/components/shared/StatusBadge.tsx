import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: string
  className?: string
}

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  open: { label: 'OPEN', className: 'bg-red-50 text-red-700 border-red-200' },
  acknowledged: { label: 'ACK', className: 'bg-yellow-50 text-yellow-700 border-yellow-200' },
  investigating: { label: 'INVESTIGATING', className: 'bg-orange-50 text-orange-700 border-orange-200' },
  resolved: { label: 'RESOLVED', className: 'bg-green-50 text-green-700 border-green-200' },
  healthy: { label: 'HEALTHY', className: 'bg-green-50 text-green-700 border-green-200' },
  degraded: { label: 'DEGRADED', className: 'bg-yellow-50 text-yellow-700 border-yellow-200' },
  down: { label: 'DOWN', className: 'bg-red-50 text-red-700 border-red-200' },
  unknown: { label: 'UNKNOWN', className: 'bg-gray-50 text-gray-600 border-gray-200' },
  success: { label: 'SUCCESS', className: 'bg-green-50 text-green-700 border-green-200' },
  failed: { label: 'FAILED', className: 'bg-red-50 text-red-700 border-red-200' },
  pending: { label: 'PENDING', className: 'bg-gray-50 text-gray-600 border-gray-200' },
  matched: { label: 'MATCHED', className: 'bg-green-50 text-green-700 border-green-200' },
  mismatched: { label: 'MISMATCH', className: 'bg-red-50 text-red-700 border-red-200' },
  unmatched: { label: 'UNMATCHED', className: 'bg-orange-50 text-orange-700 border-orange-200' },
}

export default function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? { label: status.toUpperCase(), className: 'bg-gray-500/10 text-gray-400 border-gray-500/30' }

  return (
    <span className={cn('inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-medium border tracking-wider', config.className, className)}>
      {config.label}
    </span>
  )
}
