import { formatNGN } from '@/lib/utils'
import { cn } from '@/lib/utils'

interface AmountDisplayProps {
  amount: number
  className?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  highlight?: boolean
}

export default function AmountDisplay({ amount, className, size = 'md', highlight }: AmountDisplayProps) {
  const sizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
    xl: 'text-2xl font-bold',
  }

  return (
    <span className={cn(
      'font-mono tabular-nums',
      sizeClasses[size],
      highlight ? 'text-green-400' : 'text-gray-200',
      className
    )}>
      {formatNGN(amount)}
    </span>
  )
}
