'use client'

import { useState, useRef, useEffect } from 'react'
import Shell from '@/components/layout/Shell'
import ChatInput from '@/components/ai/ChatInput'
import ChatMessage from '@/components/ai/ChatMessage'
import { useAIQuery } from '@/hooks/useAI'
import { Zap } from 'lucide-react'
import type { AIQueryResponse } from '@/types/api'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content?: string
  response?: AIQueryResponse
  loading?: boolean
}

const QUICK_QUERIES = [
  'Why is my money at risk?',
  'Which provider is causing most problems?',
  'What should I do first today?',
  'Show all unresolved money issues',
]

export default function AIPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      response: {
        answer: 'Hello! I\'m the BomiPay Operations AI. I can help you investigate payment issues, analyze provider performance, reconcile transactions, and prioritize operational tasks. What would you like to know?',
        confidence: 100,
        sources: [],
        suggested_actions: [],
        tokens_used: 0,
        model: 'gpt-4',
      },
    },
  ])

  const aiQuery = useAIQuery()
  const bottomRef = useRef<HTMLDivElement>(null)
  const idCounterRef = useRef(0)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendQuery = async (query: string) => {
    const id = ++idCounterRef.current
    const userMsg: Message = { id: `u-${id}`, role: 'user', content: query }
    const loadingMsg: Message = { id: `a-${id}`, role: 'assistant', loading: true }

    setMessages((prev) => [...prev, userMsg, loadingMsg])

    try {
      const response = await aiQuery.mutateAsync({ query })
      setMessages((prev) =>
        prev.map((m) => (m.id === loadingMsg.id ? { ...m, loading: false, response } : m))
      )
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, loading: false, response: { answer: 'I encountered an error processing your request. Please try again.', confidence: 0, sources: [], suggested_actions: [], tokens_used: 0, model: 'error' } }
            : m
        )
      )
    }
  }

  const totalTokens = messages.reduce((sum, m) => sum + (m.response?.tokens_used ?? 0), 0)

  return (
    <Shell title="AI Operations Assistant">
      <div className="flex flex-col h-[calc(100vh-8rem)]">
        {/* Quick Queries */}
        <div className="flex flex-wrap gap-2 mb-4">
          <Zap className="w-3.5 h-3.5 text-yellow-500 self-center flex-shrink-0" />
          {QUICK_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => sendQuery(q)}
              disabled={aiQuery.isPending}
              className="px-3 py-1.5 rounded-lg bg-white border border-gray-200 text-xs text-gray-600 hover:text-blue-600 hover:border-blue-200 hover:bg-blue-50 transition-colors disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-auto space-y-4 pr-1">
          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              role={msg.role}
              content={msg.content}
              response={msg.response}
              isLoading={msg.loading}
            />
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <ChatInput onSubmit={sendQuery} disabled={aiQuery.isPending} />
          <div className="flex items-center justify-between mt-2 px-1">
            <span className="text-[10px] text-gray-600">Press Shift+Enter for new line</span>
            <span className="text-[10px] text-gray-600 font-mono">{totalTokens.toLocaleString()} tokens used</span>
          </div>
        </div>
      </div>
    </Shell>
  )
}
