interface ConfidenceBarProps {
  confidence: number
}

export default function ConfidenceBar({ confidence }: ConfidenceBarProps) {
  const color =
    confidence >= 80 ? 'bg-green-500' :
    confidence >= 60 ? 'bg-yellow-500' :
    'bg-red-500'

  const label =
    confidence >= 80 ? 'High' :
    confidence >= 60 ? 'Medium' :
    'Low'

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${confidence}%` }} />
      </div>
      <span className={`text-[10px] font-mono ${
        confidence >= 80 ? 'text-green-400' : confidence >= 60 ? 'text-yellow-400' : 'text-red-400'
      }`}>
        {confidence}% · {label}
      </span>
    </div>
  )
}
