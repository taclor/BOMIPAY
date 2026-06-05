import api from './api'
import type { LoginRequest, LoginResponse, RegisterRequest } from '@/types/api'

export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/login', credentials)
  if (typeof window !== 'undefined') {
    localStorage.setItem('token', data.access_token)
    if (data.user) {
      localStorage.setItem('user', JSON.stringify(data.user))
    }
  }
  return data
}

export async function register(payload: RegisterRequest): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/register', payload)
  if (typeof window !== 'undefined') {
    localStorage.setItem('token', data.access_token)
    if (data.user) {
      localStorage.setItem('user', JSON.stringify(data.user))
    }
  }
  return data
}

export function logout(): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
  }
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('token')
}

export function isAuthenticated(): boolean {
  return !!getToken()
}
