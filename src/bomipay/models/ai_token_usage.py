"""Token usage tracking for AI queries."""
import uuid

from sqlalchemy import Column, DateTime, Integer, func

from .base import TimestampMixin
from ..db import Base, GUID


class AITokenUsage(Base, TimestampMixin):
    """Track token usage and costs for each AI query."""
    __tablename__ = "ai_token_usage"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), nullable=False, index=True)
    ai_response_log_id = Column(GUID(), nullable=False, index=True)
    query_tokens = Column(Integer, nullable=False)
    response_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    cost_cents = Column(Integer, nullable=False)  # (total_tokens * rate) / 100
    model_name = Column(Integer, nullable=False, default=3)  # e.g., 3 for gpt-3.5
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "merchant_id": str(self.merchant_id),
            "ai_response_log_id": str(self.ai_response_log_id),
            "query_tokens": self.query_tokens,
            "response_tokens": self.response_tokens,
            "total_tokens": self.total_tokens,
            "cost_cents": self.cost_cents,
            "model_name": self.model_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
