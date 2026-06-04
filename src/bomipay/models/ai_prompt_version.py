"""AI Prompt versioning and response logging models."""
import uuid

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, func

from .base import TimestampMixin
from ..db import Base, GUID


class AIPromptVersion(Base, TimestampMixin):
    """Store different versions of prompts and their retrieval sources."""
    __tablename__ = "ai_prompt_versions"

    version = Column(Integer, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    model_name = Column(String(100), nullable=False)
    prompt_template = Column(Text, nullable=False)
    retrieval_sources = Column(JSON, nullable=False)  # ["incidents", "bank_statements", ...]
    safety_flags = Column(JSON, nullable=False, server_default="{}")


class AIResponseLog(Base, TimestampMixin):
    """Log all AI responses for audit trail and analysis."""
    __tablename__ = "ai_response_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(GUID(), nullable=False, index=True)
    prompt_version = Column(Integer, nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    query = Column(Text, nullable=False)
    context_sources = Column(JSON, nullable=False)  # {"incidents": [...], "transactions": [...]}
    response_text = Column(Text, nullable=False)
    confidence_score = Column(Integer, nullable=False)  # 0-10000 basis points
    has_hallucinations = Column(Integer, nullable=False, default=0)  # Boolean as int
    cited_record_ids = Column(JSON, nullable=False)  # [{"type": "incident", "id": "..."}, ...]
    retrieval_query = Column(Text, nullable=True)  # Actual SQL or query used
    response_metadata = Column(JSON, nullable=False, server_default="{}")  # Additional context
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "merchant_id": str(self.merchant_id),
            "prompt_version": self.prompt_version,
            "model_name": self.model_name,
            "query": self.query,
            "context_sources": self.context_sources,
            "response_text": self.response_text,
            "confidence_score": self.confidence_score,
            "has_hallucinations": bool(self.has_hallucinations),
            "cited_record_ids": self.cited_record_ids,
            "retrieval_query": self.retrieval_query,
            "response_metadata": self.response_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
