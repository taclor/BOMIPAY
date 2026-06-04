'use client'

import { Brain, TrendingUp, Zap } from 'lucide-react'
import type { AISummary } from '@/types/api'

interface AIInsightPanelProps {
  summary: AISummary
}

export default function AIInsightPanel({ summary }: AIInsightPanelProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2">
        <Brain className="w-4 h-4 text-purple-400 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-gray-300 leading-relaxed">{summary.summary}</p>
      </div>

      {summary.key_issues.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> Key Issues
          </p>
          <ul className="space-y-1">
            {summary.key_issues.map((issue, i) => (
              <li key={i} className="text-[11px] text-gray-400 flex items-start gap-1.5">
                <span className="text-red-500 mt-0.5 flex-shrink-0">•</span>
                {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {summary.recommended_actions.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5 flex items-center gap-1">
            <Zap className="w-3 h-3" /> Recommended
          </p>
          <ul className="space-y-1">
            {summary.recommended_actions.map((action, i) => (
              <li key={i} className="text-[11px] text-blue-400 flex items-start gap-1.5">
                <span className="flex-shrink-0 mt-0.5">→</span>
                {action}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex items-center justify-between pt-1 border-t border-[#1f2937]">
        <span className="text-[10px] text-gray-600">AI Confidence</span>
        <div className="flex items-center gap-2">
          <div className="w-16 h-1 bg-[#1f2937] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${summary.confidence >= 80 ? 'bg-green-500' : summary.confidence >= 60 ? 'bg-yellow-500' : 'bg-red-500'}`}
              style={{ width: `${summary.confidence}%` }}
            />
          </div>
          <span className="text-[10px] text-gray-400 font-mono">{summary.confidence}%</span>
        </div>
      </div>
    </div>
  )
}
