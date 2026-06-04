import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: string
  className?: string
}

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  open: { label: 'OPEN', className: 'bg-red-500/10 text-red-400 border-red-500/30' },
  acknowledged: { label: 'ACK', className: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30' },
  investigating: { label: 'INVESTIGATING', className: 'bg-orange-500/10 text-orange-400 border-orange-500/30' },
  resolved: { label: 'RESOLVED', className: 'bg-green-500/10 text-green-400 border-green-500/30' },
  healthy: { label: 'HEALTHY', className: 'bg-green-500/10 text-green-400 border-green-500/30' },
  degraded: { label: 'DEGRADED', className: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30' },
  down: { label: 'DOWN', className: 'bg-red-500/10 text-red-400 border-red-500/30' },
  unknown: { label: 'UNKNOWN', className: 'bg-gray-500/10 text-gray-400 border-gray-500/30' },
  success: { label: 'SUCCESS', className: 'bg-green-500/10 text-green-400 border-green-500/30' },
  failed: { label: 'FAILED', className: 'bg-red-500/10 text-red-400 border-red-500/30' },
  pending: { label: 'PENDING', className: 'bg-gray-500/10 text-gray-400 border-gray-500/30' },
  matched: { label: 'MATCHED', className: 'bg-green-500/10 text-green-400 border-green-500/30' },
  mismatched: { label: 'MISMATCH', className: 'bg-red-500/10 text-red-400 border-red-500/30' },
  unmatched: { label: 'UNMATCHED', className: 'bg-orange-500/10 text-orange-400 border-orange-500/30' },
}

export default function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? { label: status.toUpperCase(), className: 'bg-gray-500/10 text-gray-400 border-gray-500/30' }

  return (
    <span className={cn('inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-medium border tracking-wider', config.className, className)}>
      {config.label}
    </span>
  )
}
