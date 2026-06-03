from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProviderHealthResponse(BaseModel):
    """Provider health status information."""
    provider_name: str
    status: str
    health_score: float = Field(..., ge=0, le=100, description="Health score 0-100")
    uptime_percent: float = Field(..., ge=0, le=100, description="Uptime percentage")
    sync_success_rate: float = Field(..., ge=0, le=100, description="Sync success rate")
    error_rate: float = Field(..., ge=0, le=100, description="Error rate percentage")
    last_sync_at: Optional[datetime] = None


class AlertSummary(BaseModel):
    """Alert summary for dashboard."""
    id: Optional[str] = None
    alert_type: str
    severity: str
    message: str
    created_at: Optional[datetime] = None
    status: str = "open"


class OperationalStatusResponse(BaseModel):
    """Overall system operational status."""
    overall_status: str = Field(..., description="healthy, degraded, critical")
    system_health_score: float = Field(..., ge=0, le=100)
    key_issues: List[str] = []
    last_updated: datetime


class MetricsSummaryResponse(BaseModel):
    """Time-period metrics summary."""
    period_type: str = Field(..., description="today, week, month, year")
    total_transactions: int
    total_amount_processed: float
    success_rate: float = Field(..., ge=0, le=100)
    failed_transactions: int
    pending_transactions: int
    average_settlement_time_hours: float
    total_fees_collected: float


class ActivitiesResponse(BaseModel):
    """Recent activities feed."""
    id: Optional[str] = None
    activity_type: str = Field(..., description="transaction, incident, alert, settlement")
    description: str
    severity: Optional[str] = None  # For incidents/alerts
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class PerformanceMetricsResponse(BaseModel):
    """Key performance indicators."""
    payment_success_rate: float = Field(..., ge=0, le=100)
    average_settlement_time_hours: float
    failed_transaction_count: int
    pending_settlement_count: int
    reconciliation_mismatch_count: int
    provider_health_scores: Dict[str, float]
    top_failure_reason: Optional[str] = None
    top_error_provider: Optional[str] = None


class AnomalyIndicator(BaseModel):
    """Detected anomaly information."""
    anomaly_type: str = Field(..., description="outlier_transaction, success_rate_drop, incident_spike, settlement_delay")
    severity: str = Field(..., description="low, medium, high, critical")
    description: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    detected_at: datetime


class DashboardResponse(BaseModel):
    """Complete mission control dashboard view."""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[UUID | str] = None
    merchant_id: UUID | str
    snapshot_time: datetime
    
    # Core metrics
    total_transactions_processed: int
    total_amount_processed: float
    success_rate: float = Field(..., ge=0, le=100)
    avg_settlement_time_hours: float
    
    # Status and health
    operational_status: str = Field(..., description="healthy, degraded, critical")
    system_health_score: float = Field(..., ge=0, le=100)
    
    # Provider information
    provider_statuses: List[ProviderHealthResponse]
    
    # Incidents and alerts
    incident_count_open: int
    money_at_risk_amount: float
    open_alerts: List[AlertSummary]
    
    # Reconciliation
    failed_transaction_count: int
    pending_settlements_count: int
    reconciliation_mismatches_count: int
    
    # Performance KPIs
    performance_metrics: PerformanceMetricsResponse
    
    # Recent activity
    recent_activities: List[ActivitiesResponse]
    
    # Anomalies detected
    detected_anomalies: List[AnomalyIndicator]
    
    created_at: Optional[datetime] = None


class DashboardMetricsResponse(BaseModel):
    """Metrics for different time periods."""
    today: MetricsSummaryResponse
    week: MetricsSummaryResponse
    month: MetricsSummaryResponse
    year: MetricsSummaryResponse
