from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer


class MoneyAtRiskBreakdown(BaseModel):
    """Breakdown of MAR by provider or status."""
    amount: float
    count: int


class MoneyAtRiskResponse(BaseModel):
    """Current MAR snapshot for a merchant."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[UUID | str] = None
    merchant_id: UUID | str
    period_date: date
    pending_transactions_amount: float
    pending_transactions_count: int
    unreconciled_amount: float
    unreconciled_transaction_count: int
    failed_transfers_amount: float
    failed_transfers_count: int
    total_at_risk: float
    risk_score: int
    breakdown_by_provider: dict[str, MoneyAtRiskBreakdown]
    breakdown_by_status: dict[str, MoneyAtRiskBreakdown]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_serializer('id', 'merchant_id')
    def serialize_uuid(self, value: UUID | str | None, _info) -> Optional[str]:
        return str(value) if value else None


class MoneyAtRiskTrendPoint(BaseModel):
    """Single point in time-series MAR trend."""
    period_date: str
    total_at_risk: float
    risk_score: int
    pending_amount: float
    unreconciled_amount: float
    failed_amount: float


class MoneyAtRiskTrendResponse(BaseModel):
    """Historical MAR trend over time."""
    merchant_id: str
    days: int
    trend: list[MoneyAtRiskTrendPoint]


class MoneyAtRiskBreakdownResponse(BaseModel):
    """Detailed breakdown of MAR by provider and status."""
    merchant_id: str
    period_date: date
    total_at_risk: float
    by_provider: dict[str, MoneyAtRiskBreakdown]
    by_status: dict[str, MoneyAtRiskBreakdown]


class AtRiskTransaction(BaseModel):
    """Transaction contributing to MAR."""
    id: str
    provider_name: str
    provider_transaction_id: str
    amount: int
    status: str
    created_at: str
    age_seconds: int


class MoneyAtRiskAtRiskTransactionsResponse(BaseModel):
    """List of transactions contributing to MAR."""
    merchant_id: str
    category: Optional[str]
    count: int
    transactions: list[AtRiskTransaction]


class ProjectionPoint(BaseModel):
    """Projected MAR value at a future date."""
    day: int
    projected_date: str
    projected_mar: float


class MoneyAtRiskProjectionResponse(BaseModel):
    """Estimated resolution timeline for MAR."""
    merchant_id: str
    estimated_resolution_date: Optional[str]
    days_to_resolution: Optional[int]
    daily_reduction_rate: float
    confidence: str
    reason: Optional[str]
    projection: list[ProjectionPoint]


class MoneyAtRiskAlertItem(BaseModel):
    """Single MAR alert."""
    type: str
    severity: str
    message: str
    recommendation: str
    amount: Optional[float] = None
    score: Optional[int] = None
    previous_amount: Optional[float] = None
    current_amount: Optional[float] = None
    change_percent: Optional[float] = None


class MoneyAtRiskAlertResponse(BaseModel):
    """Alerts for high MAR or worsening trends."""
    merchant_id: str
    alerts: list[MoneyAtRiskAlertItem]
    has_alerts: bool
    high_risk: bool
