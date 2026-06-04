import { cn } from '@/lib/utils'
import { AlertTriangle, AlertOctagon, AlertCircle, Info } from 'lucide-react'

interface SeverityBadgeProps {
  severity: string
  showIcon?: boolean
  className?: string
}

const SEVERITY_CONFIG: Record<string, { label: string; className: string; Icon: React.ElementType }> = {
  critical: { label: 'CRITICAL', className: 'bg-red-500/20 text-red-400 border-red-500/40', Icon: AlertOctagon },
  high: { label: 'HIGH', className: 'bg-orange-500/20 text-orange-400 border-orange-500/40', Icon: AlertTriangle },
  medium: { label: 'MEDIUM', className: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40', Icon: AlertCircle },
  low: { label: 'LOW', className: 'bg-blue-500/20 text-blue-400 border-blue-500/40', Icon: Info },
}

export default function SeverityBadge({ severity, showIcon = true, className }: SeverityBadgeProps) {
  const config = SEVERITY_CONFIG[severity] ?? SEVERITY_CONFIG['low']
  const { Icon } = config

  return (
    <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium border tracking-wider', config.className, className)}>
      {showIcon && <Icon className="w-2.5 h-2.5" />}
      {config.label}
    </span>
  )
}
