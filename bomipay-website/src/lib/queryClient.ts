import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000,        // 1 minute — don't refetch constantly
      gcTime: 5 * 60 * 1000,       // 5 minutes cache
      retry: 2,
      refetchOnWindowFocus: false,  // prevent refetch on tab switch
      refetchOnMount: true,
    },
  },
})
