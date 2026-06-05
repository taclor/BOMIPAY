import api from './api'

export interface ProviderTestRequest {
  provider_name: string
  public_key: string
  secret_key: string
  webhook_secret?: string
}

export interface ProviderTestResponse {
  success: boolean
  message?: string
}

export interface ProviderConnectRequest {
  provider_name: string
  public_key: string
  secret_key: string
  webhook_secret?: string
  environment: 'test' | 'live'
}

export interface ProviderConnectResponse {
  success: boolean
  data: {
    provider_account_id: string
    provider_name: string
    status: string
  }
}

export async function testConnection(req: ProviderTestRequest): Promise<ProviderTestResponse> {
  const response = await api.post('/providers/test-connection', {
    provider_name: req.provider_name,
    public_key: req.public_key,
    secret_key: req.secret_key,
    webhook_secret: req.webhook_secret,
  })
  return response.data
}

export async function connectProvider(req: ProviderConnectRequest): Promise<ProviderConnectResponse> {
  const response = await api.post('/providers/connect', {
    provider_name: req.provider_name,
    credentials: {
      api_key: req.public_key,
      secret_key: req.secret_key,
    },
  })
  return response.data
}

export async function listProviders() {
  const response = await api.get('/providers')
  return response.data
}

export async function disconnectProvider(providerAccountId: string) {
  await api.delete(`/providers/${providerAccountId}`)
}

export async function getProviderHealth(providerName: string) {
  const response = await api.get(`/providers/${providerName}/health`)
  return response.data
}
