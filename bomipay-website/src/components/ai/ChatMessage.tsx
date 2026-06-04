'use client'

import { User, Bot, ExternalLink } from 'lucide-react'
import ConfidenceBar from './ConfidenceBar'
import type { AIQueryResponse } from '@/types/api'

interface ChatMessageProps {
  role: 'user' | 'assistant'
  content?: string
  response?: AIQueryResponse
  isLoading?: boolean
}

export default function ChatMessage({ role, content, response, isLoading }: ChatMessageProps) {
  if (role === 'user') {
    return (
      <div className="flex gap-3 justify-end">
        <div className="max-w-lg bg-blue-600/20 border border-blue-600/30 rounded px-4 py-3">
          <p className="text-sm text-white">{content}</p>
        </div>
        <div className="w-7 h-7 rounded bg-blue-600/30 border border-blue-600/50 flex items-center justify-center flex-shrink-0">
          <User className="w-3.5 h-3.5 text-blue-400" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3">
      <div className="w-7 h-7 rounded bg-purple-600/30 border border-purple-600/50 flex items-center justify-center flex-shrink-0">
        <Bot className="w-3.5 h-3.5 text-purple-400" />
      </div>
      <div className="flex-1 bg-[#1a2332] border border-[#1f2937] rounded px-4 py-3 space-y-3">
        {isLoading ? (
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <div key={i} className="w-1.5 h-1.5 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </div>
            <span className="text-xs text-gray-500">Analyzing…</span>
          </div>
        ) : response ? (
          <>
            <p className="text-sm text-gray-200 leading-relaxed">{response.answer}</p>

            <div className="pt-2 border-t border-[#1f2937]">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Confidence</p>
              <ConfidenceBar confidence={response.confidence} />
            </div>

            {response.sources.length > 0 && (
              <div>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Sources</p>
                <div className="flex flex-wrap gap-1.5">
                  {response.sources.map((source) => (
                    <a
                      key={source.id}
                      href={source.url ?? '#'}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#1f2937] border border-[#374151] text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      <ExternalLink className="w-2.5 h-2.5" />
                      {source.title}
                    </a>
                  ))}
                </div>
              </div>
            )}

            {response.suggested_actions.length > 0 && (
              <div>
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Suggested Actions</p>
                <div className="space-y-1">
                  {response.suggested_actions.map((action, i) => (
                    <a
                      key={i}
                      href={action.url ?? '#'}
                      className="flex items-center gap-1.5 text-xs text-teal-400 hover:text-teal-300 transition-colors"
                    >
                      <span>→</span>
                      {action.label}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  )
}
