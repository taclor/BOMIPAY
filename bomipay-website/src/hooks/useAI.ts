import { useMutation } from '@tanstack/react-query'
import api from '@/lib/api'
import type { AIQueryRequest, AIQueryResponse } from '@/types/api'

export function useAIQuery() {
  return useMutation({
    mutationFn: async (request: AIQueryRequest) => {
      const { data } = await api.post<AIQueryResponse>('/ai-assistant/query', request)
      return data
    },
  })
}
