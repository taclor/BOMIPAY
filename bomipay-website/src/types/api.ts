// ──────────────────────────────────────────────
// Auth
// ──────────────────────────────────────────────
export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  full_name: string
  email: string
  phone?: string | null
  password: string
  merchant_name?: string
  business_type?: string
  country?: string
}

export interface User {
  id: string
  email: string
  full_name: string
  role: string
  merchant_id?: string | null
}

export interface LoginResponse {
  access_token: string
  refresh_token?: string
  token_type: string
  user?: User
}

// ──────────────────────────────────────────────
// Dashboard
// ──────────────────────────────────────────────
export interface DashboardSummary {
  payment_success_rate: number
  failed_transactions_count: number
  money_at_risk_amount: number
  money_at_risk_status: 'critical' | 'warning' | 'ok'
  pending_settlements_count: number
  pending_settlements_amount: number
  open_incidents_count: number
  total_transactions_24h: number
  transaction_volume_24h: number
}

export interface DashboardMetrics {
  success_rate_trend: TrendPoint[]
  failed_trend: TrendPoint[]
  volume_trend: TrendPoint[]
}

export interface TrendPoint {
  timestamp: string
  value: number
}

export interface ProviderSummary {
  name: string
  status: 'healthy' | 'degraded' | 'down' | 'unknown'
  reliability_bps: number
  latency_ms: number
  last_checked: string
}

export interface Activity {
  id: string
  type: string
  title: string
  description: string
  timestamp: string
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info'
  reference_id?: string
}

export interface AISummary {
  summary: string
  key_issues: string[]
  recommended_actions: string[]
  confidence: number
}

// ──────────────────────────────────────────────
// Timeline
// ──────────────────────────────────────────────
export type TimelineEventType =
  | 'transaction_created'
  | 'webhook_received'
  | 'status_changed'
  | 'settlement_received'
  | 'dispute_opened'
  | 'incident_created'
  | 'bank_statement_matched'

export interface TimelineEvent {
  id: string
  event_type: TimelineEventType
  transaction_id?: string
  reference?: string
  amount?: number
  currency?: string
  provider?: string
  status?: string
  description: string
  metadata?: Record<string, unknown>
  timestamp: string
}

export interface TimelineResponse {
  events: TimelineEvent[]
  next_cursor?: string
  has_more: boolean
}

// ──────────────────────────────────────────────
// Incidents
// ──────────────────────────────────────────────
export type IncidentSeverity = 'critical' | 'high' | 'medium' | 'low'
export type IncidentStatus = 'open' | 'acknowledged' | 'investigating' | 'resolved'

export interface Incident {
  id: string
  title: string
  description: string
  severity: IncidentSeverity
  status: IncidentStatus
  affected_provider?: string
  affected_transactions_count: number
  money_at_risk: number
  created_at: string
  updated_at: string
  acknowledged_at?: string
  resolved_at?: string
  ai_summary?: string
  timeline?: IncidentTimelineEntry[]
}

export interface IncidentTimelineEntry {
  id: string
  action: string
  actor?: string
  timestamp: string
  notes?: string
}

// ──────────────────────────────────────────────
// Reconciliation
// ──────────────────────────────────────────────
export type MatchStatus = 'matched' | 'mismatched' | 'pending' | 'unmatched'

export interface ReconciliationEntry {
  id: string
  provider: string
  transaction_id: string
  provider_amount: number
  bank_amount?: number
  difference?: number
  match_status: MatchStatus
  settlement_date: string
  bank_entry_id?: string
  currency: string
}

export interface BankStatementEntry {
  id: string
  date: string
  description: string
  amount: number
  balance: number
  reference?: string
  match_status: MatchStatus
  matched_transaction_id?: string
}

// ──────────────────────────────────────────────
// Action Center
// ──────────────────────────────────────────────
export type ActionType =
  | 'investigate_failed_payment'
  | 'upload_bank_statement'
  | 'resolve_unmatched_settlement'
  | 'acknowledge_incident'
  | 'open_dispute'
  | 'check_provider_sync_failure'

export interface ActionItem {
  id: string
  action_type: ActionType
  priority: number
  title: string
  description: string
  reference_id?: string
  reference_type?: string
  completed: boolean
  created_at: string
  metadata?: Record<string, unknown>
}

export interface ActionCenterResponse {
  actions: ActionItem[]
  total: number
  completed: number
  pending: number
}

// ──────────────────────────────────────────────
// Provider Health
// ──────────────────────────────────────────────
export interface ProviderHealthMetrics {
  name: string
  display_name: string
  status: 'healthy' | 'degraded' | 'down' | 'unknown'
  reliability_bps: number
  avg_latency_ms: number
  p95_latency_ms: number
  p99_latency_ms: number
  error_rate_bps: number
  uptime_bps: number
  last_incident?: string
  last_checked: string
}

export interface ProviderHealthHistory {
  provider: string
  history: ProviderHistoryPoint[]
}

export interface ProviderHistoryPoint {
  date: string
  reliability_bps: number
  latency_ms: number
  error_count: number
  outage_minutes: number
}

// ──────────────────────────────────────────────
// Payment Graph
// ──────────────────────────────────────────────
export type NodeType = 'transaction' | 'settlement' | 'dispute' | 'incident' | 'bank_entry'

export interface GraphNode {
  id: string
  type: NodeType
  label: string
  data: Record<string, unknown>
  position?: { x: number; y: number }
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  label?: string
  relationship_type?: string
}

export interface PaymentGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  transaction_id?: string
}

export interface MerchantGraphOverview {
  merchant_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  summary: Record<string, number>
}

// ──────────────────────────────────────────────
// AI Assistant
// ──────────────────────────────────────────────
export interface AIQueryRequest {
  query: string
  context?: Record<string, unknown>
}

export interface AISource {
  type: string
  id: string
  title: string
  url?: string
}

export interface AISuggestedAction {
  action: string
  label: string
  url?: string
}

export interface AIQueryResponse {
  answer: string
  confidence: number
  sources: AISource[]
  suggested_actions: AISuggestedAction[]
  tokens_used: number
  model: string
}

// ──────────────────────────────────────────────
// Generic
// ──────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface ApiError {
  detail: string
  status_code?: number
}
