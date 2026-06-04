'use client'

import { useState } from 'react'
import { Send } from 'lucide-react'

interface ChatInputProps {
  onSubmit: (query: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [value, setValue] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!value.trim() || disabled) return
    onSubmit(value.trim())
    setValue('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-end">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e) } }}
        placeholder="Ask anything about your payment operations…"
        disabled={disabled}
        rows={2}
        className="flex-1 bg-[#1f2937] border border-[#374151] rounded px-3 py-2 text-sm text-white placeholder-gray-600 resize-none focus:outline-none focus:border-blue-500/50 disabled:opacity-50 font-mono"
      />
      <button
        type="submit"
        disabled={!value.trim() || disabled}
        className="px-4 py-3 rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
      >
        <Send className="w-4 h-4" />
      </button>
    </form>
  )
}
