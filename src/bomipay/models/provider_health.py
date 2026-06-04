import enum
import uuid

from sqlalchemy import Column, Date, DateTime, Integer, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class HealthStatus(str, enum.Enum):
    healthy = "healthy"
    degraded = "degraded"
    critical = "critical"


class ProviderHealthMetrics(Base, TimestampMixin):
    __tablename__ = "provider_health_metrics"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), nullable=False, index=True)
    provider_name = Column(String(50), nullable=False, index=True)
    metric_date = Column(Date, nullable=False, index=True)

    # Transaction metrics
    transaction_count = Column(Integer, nullable=False, default=0)
    transaction_success_count = Column(Integer, nullable=False, default=0)
    transaction_fail_count = Column(Integer, nullable=False, default=0)
    transaction_avg_latency_ms = Column(Integer, nullable=False, default=0)

    # Settlement metrics
    settlement_count = Column(Integer, nullable=False, default=0)
    settlement_success_count = Column(Integer, nullable=False, default=0)
    settlement_avg_latency_ms = Column(Integer, nullable=False, default=0)
    settlement_mismatch_count = Column(Integer, nullable=False, default=0)

    # Webhook metrics
    webhook_event_count = Column(Integer, nullable=False, default=0)
    webhook_success_count = Column(Integer, nullable=False, default=0)
    webhook_fail_count = Column(Integer, nullable=False, default=0)
    webhook_avg_latency_ms = Column(Integer, nullable=False, default=0)

    # Outage tracking
    outage_windows = Column(Integer, nullable=False, default=0)
    last_outage_start_at = Column(DateTime(timezone=True), nullable=True)
    last_outage_end_at = Column(DateTime(timezone=True), nullable=True)

    # Calculated scores (basis points: 0-10000 = 0-100%)
    reliability_score_bps = Column(Integer, nullable=False, default=0)
    settlement_lag_score_bps = Column(Integer, nullable=False, default=0)
    webhook_failure_score_bps = Column(Integer, nullable=False, default=0)

    # Health status
    health_status = Column(String(20), nullable=False, default=HealthStatus.healthy.value)
