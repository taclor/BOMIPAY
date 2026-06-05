import { cn } from '@/lib/utils'
import { AlertTriangle, AlertOctagon, AlertCircle, Info } from 'lucide-react'

interface SeverityBadgeProps {
  severity: string
  showIcon?: boolean
  className?: string
}

const SEVERITY_CONFIG: Record<string, { label: string; className: string; Icon: React.ElementType }> = {
  critical: { label: 'CRITICAL', className: 'bg-red-50 text-red-700 border-red-200', Icon: AlertOctagon },
  high: { label: 'HIGH', className: 'bg-orange-50 text-orange-700 border-orange-200', Icon: AlertTriangle },
  medium: { label: 'MEDIUM', className: 'bg-yellow-50 text-yellow-700 border-yellow-200', Icon: AlertCircle },
  low: { label: 'LOW', className: 'bg-blue-50 text-blue-700 border-blue-200', Icon: Info },
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
