import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy.orm import relationship

from .base import TimestampMixin
from ..db import Base, GUID


class DashboardSnapshotStatus(str, enum.Enum):
    """Status of a dashboard snapshot."""
    active = "active"
    archived = "archived"


class DashboardSnapshot(Base, TimestampMixin):
    """Real-time Mission Control Dashboard snapshot.
    
    Captures a point-in-time aggregation of metrics, provider health,
    and operational status for a merchant.
    """
    __tablename__ = "dashboard_snapshots"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), ForeignKey("merchants.id"), nullable=False, index=True)
    snapshot_time = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Transaction metrics
    total_transactions_processed = Column(Integer, nullable=False, default=0)
    total_amount_processed = Column(Numeric(18, 2), nullable=False, default=0)
    success_rate = Column(Numeric(5, 2), nullable=False, default=0)  # 0-100
    
    # Settlement metrics
    avg_settlement_time_hours = Column(Numeric(8, 2), nullable=False, default=0)
    
    # Provider health status: {provider_name: {status, health_score, uptime}}
    provider_statuses = Column(JSON, nullable=True, default=dict)
    
    # Incident and alert tracking
    incident_count_open = Column(Integer, nullable=False, default=0)
    money_at_risk_amount = Column(Numeric(18, 2), nullable=False, default=0)
    
    # Active alerts (JSON array)
    alerts = Column(JSON, nullable=True, default=list)
    
    # Performance KPIs
    failed_transaction_count = Column(Integer, nullable=False, default=0)
    pending_settlements_count = Column(Integer, nullable=False, default=0)
    reconciliation_mismatches_count = Column(Integer, nullable=False, default=0)
    
    # Anomaly indicators
    anomaly_indicators = Column(JSON, nullable=True, default=dict)
    
    status = Column(String(32), nullable=False, default=DashboardSnapshotStatus.active.value)
    
    __table_args__ = (
        # Index for merchant's latest snapshot lookup
        # Index for time-range queries
    )
