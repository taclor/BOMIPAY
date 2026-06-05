import { useAuthStore } from '@/store/authStore'

export function useAuth() {
  const { token, user, isAuthenticated, _hydrated } = useAuthStore()
  return { token, user, isAuthenticated, isLoading: !_hydrated }
}
