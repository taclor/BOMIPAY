"""
AI Observability — token usage tracking and cost analysis.

Tracks:
- Query tokens (input)
- Response tokens (output)
- Total tokens consumed
- Estimated cost (tokens * rate)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ai_token_usage import AITokenUsage

logger = logging.getLogger("bomipay")


# Standard token costs per 1K tokens (in cents) — adjust as needed
TOKEN_COSTS = {
    "gpt-3.5-turbo": 0.15,  # $0.0015 per 1K input tokens
    "gpt-4": 1.5,  # $0.015 per 1K input tokens
    "claude-2": 0.8,  # $0.008 per 1K tokens
}


class AITokenCounter:
    """Estimate and track token usage for AI queries."""

    @staticmethod
    def estimate_tokens_for_text(text: str) -> int:
        """
        Rough estimate of tokens for text.
        Rule of thumb: ~1 token per 4 characters
        """
        if not text:
            return 0
        return max(1, len(text) // 4)

    @staticmethod
    def estimate_context_tokens(context: Dict) -> int:
        """Estimate tokens consumed by context data."""
        if not context:
            return 0

        total = 0

        # Estimate per key
        for key, value in context.items():
            if isinstance(value, str):
                total += AITokenCounter.estimate_tokens_for_text(value)
            elif isinstance(value, (list, dict)):
                total += AITokenCounter.estimate_tokens_for_text(str(value))
            elif isinstance(value, (int, float)):
                total += 1

        return total

    @staticmethod
    def estimate_response_tokens(response: str) -> int:
        """Estimate tokens in AI response."""
        return AITokenCounter.estimate_tokens_for_text(response)

    @staticmethod
    def calculate_cost_cents(
        total_tokens: int,
        model_name: str = "gpt-3.5-turbo",
    ) -> int:
        """
        Calculate estimated cost in cents.

        Args:
            total_tokens: Total tokens used
            model_name: Model name (e.g., "gpt-3.5-turbo")

        Returns:
            Cost in cents
        """
        rate_per_1k = TOKEN_COSTS.get(model_name, 0.15)
        cost = (total_tokens * rate_per_1k) / 1000
        return int(round(cost))

    @staticmethod
    async def log_token_usage(
        db: AsyncSession,
        merchant_id: str,
        ai_response_log_id: str,
        query_tokens: int,
        response_tokens: int,
        model_name: str = "gpt-3.5-turbo",
    ) -> AITokenUsage:
        """
        Log token usage to database.

        Args:
            db: Database session
            merchant_id: Merchant ID
            ai_response_log_id: Reference to AIResponseLog
            query_tokens: Tokens in query
            response_tokens: Tokens in response
            model_name: Model name

        Returns:
            Created AITokenUsage record
        """
        total_tokens = query_tokens + response_tokens
        cost_cents = AITokenCounter.calculate_cost_cents(total_tokens, model_name)

        token_usage = AITokenUsage(
            merchant_id=merchant_id,
            ai_response_log_id=ai_response_log_id,
            query_tokens=query_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
            cost_cents=cost_cents,
            model_name=model_name,
        )

        db.add(token_usage)
        await db.flush()

        logger.info(
            "ai_token_usage.logged",
            extra={
                "merchant_id": merchant_id,
                "total_tokens": total_tokens,
                "cost_cents": cost_cents,
            }
        )

        return token_usage


class AITokenAnalytics:
    """Analyze token usage patterns and costs."""

    @staticmethod
    async def get_token_usage_summary(
        db: AsyncSession,
        merchant_id: str,
        days: int = 7,
    ) -> Dict:
        """
        Get token usage summary for a merchant over N days.

        Returns:
            {
                "total_queries": int,
                "total_tokens": int,
                "total_cost_cents": int,
                "avg_tokens_per_query": float,
                "avg_cost_per_query_cents": float,
                "by_model": {model_name: {...}},
            }
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Total queries and tokens
        result = await db.execute(
            select(
                func.count(AITokenUsage.id).label("count"),
                func.sum(AITokenUsage.total_tokens).label("total_tokens"),
                func.sum(AITokenUsage.cost_cents).label("total_cost"),
            ).where(
                AITokenUsage.merchant_id == merchant_id,
                AITokenUsage.created_at >= cutoff_date,
            )
        )
        row = result.one()
        total_queries = row.count or 0
        total_tokens = row.total_tokens or 0
        total_cost = row.total_cost or 0

        # By model
        by_model_result = await db.execute(
            select(
                AITokenUsage.model_name,
                func.count(AITokenUsage.id).label("count"),
                func.sum(AITokenUsage.total_tokens).label("total_tokens"),
                func.sum(AITokenUsage.cost_cents).label("total_cost"),
            ).where(
                AITokenUsage.merchant_id == merchant_id,
                AITokenUsage.created_at >= cutoff_date,
            ).group_by(AITokenUsage.model_name)
        )

        by_model = {}
        for row in by_model_result.all():
            by_model[row.model_name] = {
                "count": row.count,
                "total_tokens": row.total_tokens or 0,
                "total_cost_cents": row.total_cost or 0,
            }

        avg_tokens_per_query = (total_tokens / total_queries) if total_queries > 0 else 0
        avg_cost_per_query = (total_cost / total_queries) if total_queries > 0 else 0

        return {
            "total_queries": total_queries,
            "total_tokens": total_tokens,
            "total_cost_cents": total_cost,
            "avg_tokens_per_query": round(avg_tokens_per_query, 2),
            "avg_cost_per_query_cents": round(avg_cost_per_query, 2),
            "by_model": by_model,
            "period_days": days,
        }

    @staticmethod
    async def get_top_merchants_by_token_usage(
        db: AsyncSession,
        days: int = 7,
        limit: int = 10,
    ) -> list:
        """
        Get top merchants by token usage (for system-wide analysis).

        Returns:
            List of {merchant_id, total_tokens, total_cost_cents, query_count}
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        result = await db.execute(
            select(
                AITokenUsage.merchant_id,
                func.sum(AITokenUsage.total_tokens).label("total_tokens"),
                func.sum(AITokenUsage.cost_cents).label("total_cost"),
                func.count(AITokenUsage.id).label("count"),
            ).where(
                AITokenUsage.created_at >= cutoff_date,
            ).group_by(AITokenUsage.merchant_id)
            .order_by(func.sum(AITokenUsage.total_tokens).desc())
            .limit(limit)
        )

        return [
            {
                "merchant_id": str(row.merchant_id),
                "total_tokens": row.total_tokens or 0,
                "total_cost_cents": row.total_cost or 0,
                "query_count": row.count or 0,
            }
            for row in result.all()
        ]
