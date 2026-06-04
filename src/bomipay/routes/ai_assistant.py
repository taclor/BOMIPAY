import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..services.auth import require_role
from ..services.ai_assistant import AIAssistantService
from ..services.ai_observability import AITokenAnalytics
from ..models.ai_prompt_version import AIResponseLog

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["AI Assistant"])

ALLOWED_ROLES = (Role.admin, Role.merchant_user, Role.finance, Role.support)


class AIQueryRequest(BaseModel):
    merchant_id: Optional[str] = None
    query: str
    transaction_id: Optional[str] = None
    settlement_id: Optional[str] = None


class SafetyCheckRequest(BaseModel):
    query: str


def _check_merchant_access(current_user, merchant_id: str):
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.get("/ai-assistant/health")
async def ai_health():
    categories = AIAssistantService.get_categories()
    return {"status": "ok", "categories_supported": len(categories), "version": "1.0"}


@router.get("/ai-assistant/categories")
async def ai_categories():
    return {"categories": AIAssistantService.get_categories()}


@router.post("/ai-assistant/query")
async def ai_query(
    payload: AIQueryRequest,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    merchant_id = str(payload.merchant_id or current_user.merchant_id or "")
    if not merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, merchant_id)

    result = await AIAssistantService.query(
        db,
        merchant_id=merchant_id,
        query=payload.query,
        transaction_id=payload.transaction_id,
        settlement_id=payload.settlement_id,
    )
    return result


@router.post("/ai-assistant/query-with-safety")
async def ai_query_with_safety(
    payload: AIQueryRequest,
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute AI query with full safety checks, hallucination detection, and token tracking.

    Returns:
        {
            "response": "...",
            "confidence_score_bps": 8500,
            "sources": ["incident_123", ...],
            "token_usage": {"query": 50, "response": 100, "total": 150, "cost_cents": 5},
            "caveats": [...],
            "is_safe": true,
            "has_hallucinations": false,
            "response_log_id": "..."
        }
    """
    merchant_id = str(payload.merchant_id or current_user.merchant_id or "")
    if not merchant_id:
        raise HTTPException(status_code=400, detail="merchant_id is required")
    _check_merchant_access(current_user, merchant_id)

    result = await AIAssistantService.query_with_safety(
        db,
        merchant_id=merchant_id,
        query=payload.query,
        transaction_id=payload.transaction_id,
        settlement_id=payload.settlement_id,
    )
    await db.commit()
    return result


@router.get("/ai-assistant/safety-check")
async def ai_safety_check(
    query: str = Query(..., min_length=1),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
):
    """
    Check if a query is safe to execute.

    Returns:
        {
            "safe": bool,
            "reasons": [str],
            "suggestions": [str]
        }
    """
    from ..services.ai_safety import AISafetyChecker

    # Basic safety checks without DB context
    reasons = []
    suggestions = []

    query_lower = query.lower()

    # Check 1: SQL injection patterns
    sql_keywords = ["drop", "delete", "truncate", "alter", "update"]
    for keyword in sql_keywords:
        if keyword in query_lower:
            reasons.append(f"Query contains potentially dangerous keyword: {keyword}")

    # Check 2: Extremely long queries (possible dos attack)
    if len(query) > 5000:
        reasons.append("Query is unusually long (>5000 chars) — possible attack")

    # Check 3: Special characters
    dangerous_chars = ["<script", "javascript:", "onerror="]
    for char in dangerous_chars:
        if char in query_lower:
            reasons.append(f"Query contains suspicious pattern: {char}")

    is_safe = len(reasons) == 0

    if not is_safe:
        suggestions.append("Query was flagged as potentially unsafe — review before executing")
    else:
        suggestions.append("Query appears safe to execute")

    return {
        "safe": is_safe,
        "reasons": reasons,
        "suggestions": suggestions,
    }


@router.get("/ai-assistant/token-usage")
async def ai_token_usage(
    merchant_id: str = Query(...),
    days: int = Query(7, ge=1, le=90),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get token usage and cost summary for a merchant.

    Returns:
        {
            "total_queries": 123,
            "total_tokens": 5000,
            "total_cost_cents": 1234,
            "avg_tokens_per_query": 40.65,
            "avg_cost_per_query_cents": 10.03,
            "by_model": {
                "gpt-3.5-turbo": {"count": 100, "total_tokens": 4000, "total_cost_cents": 900}
            },
            "period_days": 7
        }
    """
    _check_merchant_access(current_user, merchant_id)

    usage_summary = await AITokenAnalytics.get_token_usage_summary(
        db,
        merchant_id=merchant_id,
        days=days,
    )

    return usage_summary


@router.get("/ai-assistant/audit-log")
async def ai_audit_log(
    merchant_id: str = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user=Depends(require_role(*ALLOWED_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated AI response audit log for a merchant.

    Returns:
        {
            "total": 123,
            "skip": 0,
            "limit": 10,
            "items": [
                {
                    "id": "...",
                    "query": "...",
                    "response_text": "...",
                    "confidence_score": 8500,
                    "has_hallucinations": false,
                    "cited_record_ids": [...],
                    "created_at": "2024-01-17T...",
                    ...
                }
            ]
        }
    """
    from sqlalchemy import func, select

    _check_merchant_access(current_user, merchant_id)

    # Get total count
    count_result = await db.execute(
        select(func.count(AIResponseLog.id)).where(
            AIResponseLog.merchant_id == merchant_id
        )
    )
    total = count_result.scalar() or 0

    # Get paginated results
    result = await db.execute(
        select(AIResponseLog)
        .where(AIResponseLog.merchant_id == merchant_id)
        .order_by(AIResponseLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    logs = list(result.scalars().all())

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [log.to_dict() for log in logs],
    }
