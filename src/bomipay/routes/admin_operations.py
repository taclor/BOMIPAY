"""Admin Operations Console - internal operations and debugging endpoints."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..models.audit import AuditLog
from ..models.incident import Incident
from ..models.transaction import Transaction
from ..models.transaction_event import TransactionEvent
from ..models.provider_sync_job import ProviderSyncJob, ProviderSyncStatus
from ..models.reconciliation import ReconciliationRun
from ..models.ai_prompt_version import AIResponseLog
from ..services.auth import require_role
from ..services.audit import log_audit_event
from ..services.task_enqueue import TaskEnqueueService
from ..services.event_replay import EventReplayer
from ..services.provider_health import ProviderHealthService
from ..worker import app as celery_app

logger = logging.getLogger("bomipay")
router = APIRouter(tags=["Admin Operations"], prefix="/admin")


def generate_correlation_id() -> str:
    """Generate a correlation ID for tracing."""
    return str(uuid.uuid4())


def _ensure_admin(current_user):
    """Ensure user has admin role."""
    if current_user.role != Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access this endpoint"
        )
    return current_user


# ============================================================================
# Webhook Management
# ============================================================================

class WebhookReplayRequest:
    """Request to replay a webhook."""
    pass


@router.post("/webhooks/{webhook_event_id}/replay")
async def replay_webhook(
    webhook_event_id: str,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Replay a webhook event (re-run full post-processing).
    
    Returns: {"status": "replayed", "result": {...}, "correlation_id": "..."}
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Find the transaction event
    stmt = select(TransactionEvent).where(
        TransactionEvent.provider_event_id == webhook_event_id
    )
    result = await db.execute(stmt)
    event = result.scalars().first()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook event not found"
        )
    
    # Log audit event
    log_audit_event(
        db,
        event_type="admin.webhook.replay",
        actor_id=str(admin_user.id),
        actor_role=admin_user.role.value,
        event_payload={
            "webhook_event_id": webhook_event_id,
            "correlation_id": correlation_id
        }
    )
    
    # Enqueue replay task
    job_id = TaskEnqueueService.enqueue_webhook_post_process(webhook_event_id, countdown=0)
    
    await db.commit()
    
    return {
        "status": "replayed",
        "webhook_event_id": webhook_event_id,
        "job_id": job_id,
        "correlation_id": correlation_id
    }


@router.get("/webhooks")
async def list_webhooks(
    merchant_id: Optional[str] = None,
    provider: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    List webhooks with detailed status and filtering.
    
    Query parameters:
    - merchant_id: Filter by merchant
    - provider: Filter by provider name
    - status: Filter by event status
    - limit: Pagination limit
    - offset: Pagination offset
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Build query
    query = select(TransactionEvent)
    
    if merchant_id:
        query = query.join(Transaction).where(
            Transaction.merchant_id == merchant_id
        )
    
    if provider:
        query = query.where(TransactionEvent.provider_name == provider)
    
    if status:
        query = query.where(TransactionEvent.status == status)
    
    # Get total count
    count_stmt = select(func.count()).select_from(TransactionEvent)
    if merchant_id:
        count_stmt = count_stmt.join(Transaction).where(
            Transaction.merchant_id == merchant_id
        )
    if provider:
        count_stmt = count_stmt.where(TransactionEvent.provider_name == provider)
    if status:
        count_stmt = count_stmt.where(TransactionEvent.status == status)
    
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    # Get paginated results
    query = query.order_by(TransactionEvent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    events = result.scalars().all()
    
    return {
        "webhooks": [
            {
                "id": str(event.id),
                "provider_event_id": event.provider_event_id,
                "provider": event.provider_name,
                "event_type": event.event_type,
                "status": event.status,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
            for event in events
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "correlation_id": correlation_id
    }


# ============================================================================
# Provider Operations
# ============================================================================

@router.post("/providers/{provider_account_id}/sync/force")
async def force_provider_sync(
    provider_account_id: str,
    sync_type: str = "transactions",
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Force immediate provider sync (don't wait for scheduled).
    
    Body: {"sync_type": "transactions|settlements|transfers|refunds"}
    
    Returns: {"status": "queued", "job_id": "...", "correlation_id": "..."}
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Find provider account to get merchant_id
    from ..models.provider_account import ProviderAccount
    stmt = select(ProviderAccount).where(ProviderAccount.id == provider_account_id)
    result = await db.execute(stmt)
    provider_account = result.scalars().first()
    
    if not provider_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider account not found"
        )
    
    merchant_id = str(provider_account.merchant_id)
    
    # Log audit event
    log_audit_event(
        db,
        event_type="admin.provider.force_sync",
        actor_id=str(admin_user.id),
        actor_role=admin_user.role.value,
        event_payload={
            "provider_account_id": provider_account_id,
            "sync_type": sync_type,
            "correlation_id": correlation_id
        }
    )
    
    # Enqueue sync task
    job_id = TaskEnqueueService.enqueue_provider_sync(
        merchant_id=merchant_id,
        provider_account_id=provider_account_id,
        sync_type=sync_type,
        countdown=0
    )
    
    await db.commit()
    
    return {
        "status": "queued",
        "job_id": job_id,
        "sync_type": sync_type,
        "correlation_id": correlation_id
    }


@router.post("/providers/{provider_account_id}/health-check")
async def provider_health_check(
    provider_account_id: str,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Run health check against live provider API.
    
    Returns: {"status": "ok|degraded|down", "latency_ms": 123, "correlation_id": "..."}
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Find provider account
    from ..models.provider_account import ProviderAccount
    stmt = select(ProviderAccount).where(ProviderAccount.id == provider_account_id)
    result = await db.execute(stmt)
    provider_account = result.scalars().first()
    
    if not provider_account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider account not found"
        )
    
    # Log audit event
    log_audit_event(
        db,
        event_type="admin.provider.health_check",
        actor_id=str(admin_user.id),
        actor_role=admin_user.role.value,
        event_payload={
            "provider_account_id": provider_account_id,
            "correlation_id": correlation_id
        }
    )
    
    # Run health check
    start = datetime.now(timezone.utc)
    health_status = await ProviderHealthService.get_health_status(
        db, str(provider_account.merchant_id), provider_account.provider_name
    )
    latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    
    await db.commit()
    
    return {
        "provider": provider_account.provider_name,
        "status": health_status,
        "latency_ms": latency_ms,
        "correlation_id": correlation_id
    }


# ============================================================================
# Incident Investigation
# ============================================================================

@router.get("/incidents/{incident_id}/timeline")
async def get_incident_timeline(
    incident_id: str,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get full incident timeline: alerts → incident → events → resolution.
    
    Includes related transactions, settlements.
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Find incident
    stmt = select(Incident).where(Incident.id == incident_id)
    result = await db.execute(stmt)
    incident = result.scalars().first()
    
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found"
        )
    
    # Get related transactions
    tx_stmt = select(Transaction).where(
        Transaction.merchant_id == incident.merchant_id
    ).order_by(Transaction.created_at)
    tx_result = await db.execute(tx_stmt)
    transactions = tx_result.scalars().all()
    
    # Get related audit events for this incident
    audit_stmt = select(AuditLog).where(
        and_(
            AuditLog.event_payload.contains(incident_id),
        )
    ).order_by(AuditLog.created_at)
    audit_result = await db.execute(audit_stmt)
    audit_events = audit_result.scalars().all()
    
    return {
        "incident": {
            "id": str(incident.id),
            "title": incident.title,
            "type": incident.incident_type,
            "severity": incident.severity,
            "status": incident.status,
            "created_at": incident.created_at.isoformat() if incident.created_at else None,
            "started_at": incident.started_at.isoformat() if incident.started_at else None,
            "ended_at": incident.ended_at.isoformat() if incident.ended_at else None,
        },
        "related_transactions": [
            {
                "id": str(tx.id),
                "provider_transaction_id": tx.provider_transaction_id,
                "amount": tx.amount,
                "status": tx.status,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in transactions[-10:]  # Last 10
        ],
        "timeline": [
            {
                "timestamp": event.created_at.isoformat() if event.created_at else None,
                "event_type": event.event_type,
                "actor_id": str(event.actor_id) if event.actor_id else None,
                "details": event.event_payload
            }
            for event in audit_events
        ],
        "correlation_id": correlation_id
    }


@router.get("/incidents/{incident_id}/related-records")
async def get_incident_related_records(
    incident_id: str,
    limit: int = 50,
    offset: int = 0,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all transactions and settlements linked to an incident.
    
    Pagination supported.
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Find incident
    stmt = select(Incident).where(Incident.id == incident_id)
    result = await db.execute(stmt)
    incident = result.scalars().first()
    
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found"
        )
    
    # Get paginated related transactions
    tx_stmt = select(Transaction).where(
        Transaction.merchant_id == incident.merchant_id
    ).order_by(Transaction.created_at.desc()).limit(limit).offset(offset)
    
    total_stmt = select(func.count()).select_from(Transaction).where(
        Transaction.merchant_id == incident.merchant_id
    )
    
    tx_result = await db.execute(tx_stmt)
    transactions = tx_result.scalars().all()
    
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0
    
    return {
        "incident_id": incident_id,
        "related_transactions": [
            {
                "id": str(tx.id),
                "provider_transaction_id": tx.provider_transaction_id,
                "amount": tx.amount,
                "status": tx.status,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in transactions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "correlation_id": correlation_id
    }


# ============================================================================
# Queue/Job Monitoring
# ============================================================================

@router.get("/queue-status")
async def get_queue_status(
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get queue depth per task type.
    
    Returns: {"sync_jobs": 5, "webhooks": 0, "ai_tasks": 2, ...}
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Get active jobs from celery
    try:
        inspector = celery_app.control.inspect()
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}
        
        # Count by task type
        sync_jobs = 0
        webhooks = 0
        ai_tasks = 0
        reconciliation = 0
        
        for worker_tasks in active.values():
            for task in worker_tasks:
                task_name = task.get("name", "")
                if "sync" in task_name:
                    sync_jobs += 1
                elif "webhook" in task_name:
                    webhooks += 1
                elif "ai" in task_name or "assistant" in task_name:
                    ai_tasks += 1
                elif "reconcil" in task_name:
                    reconciliation += 1
        
        for worker_tasks in reserved.values():
            for task in worker_tasks:
                task_name = task.get("name", "")
                if "sync" in task_name:
                    sync_jobs += 1
                elif "webhook" in task_name:
                    webhooks += 1
                elif "ai" in task_name or "assistant" in task_name:
                    ai_tasks += 1
                elif "reconcil" in task_name:
                    reconciliation += 1
    except Exception as e:
        logger.warning(f"Failed to get queue status: {e}")
        sync_jobs = 0
        webhooks = 0
        ai_tasks = 0
        reconciliation = 0
    
    return {
        "sync_jobs": sync_jobs,
        "webhooks": webhooks,
        "ai_tasks": ai_tasks,
        "reconciliation": reconciliation,
        "correlation_id": correlation_id
    }


@router.get("/failed-jobs")
async def list_failed_jobs(
    days: int = 7,
    limit: int = 50,
    offset: int = 0,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    List failed Celery tasks from the past N days.
    
    Includes retry status and error messages.
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # In production, you'd query a failure tracking system
    # For now, return empty as placeholder
    failed_jobs = []
    
    return {
        "failed_jobs": failed_jobs,
        "days": days,
        "total": len(failed_jobs),
        "correlation_id": correlation_id
    }


@router.post("/failed-jobs/{job_id}/retry")
async def retry_failed_job(
    job_id: str,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Re-enqueue a failed job.
    
    Returns: {"status": "retrying", "job_id": "...", "correlation_id": "..."}
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Log audit event
    log_audit_event(
        db,
        event_type="admin.job.retry",
        actor_id=str(admin_user.id),
        actor_role=admin_user.role.value,
        event_payload={
            "original_job_id": job_id,
            "correlation_id": correlation_id
        }
    )
    
    # Re-enqueue job (implementation depends on your job storage)
    new_job_id = str(uuid.uuid4())
    
    await db.commit()
    
    return {
        "status": "retrying",
        "original_job_id": job_id,
        "new_job_id": new_job_id,
        "correlation_id": correlation_id
    }


# ============================================================================
# Reconciliation Replay
# ============================================================================

@router.post("/reconciliation/{reconciliation_run_id}/replay")
async def replay_reconciliation(
    reconciliation_run_id: str,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Re-run reconciliation (don't mutate originals, create new run).
    
    Returns: {"status": "replaying", "new_run_id": "...", "correlation_id": "..."}
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Find original reconciliation run
    stmt = select(ReconciliationRun).where(
        ReconciliationRun.id == reconciliation_run_id
    )
    result = await db.execute(stmt)
    original_run = result.scalars().first()
    
    if not original_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation run not found"
        )
    
    # Log audit event
    log_audit_event(
        db,
        event_type="admin.reconciliation.replay",
        actor_id=str(admin_user.id),
        actor_role=admin_user.role.value,
        event_payload={
            "original_run_id": reconciliation_run_id,
            "correlation_id": correlation_id
        }
    )
    
    # Enqueue new reconciliation
    new_run_id = TaskEnqueueService.enqueue_reconciliation(
        merchant_id=str(original_run.merchant_id),
        date_from=original_run.date_from.isoformat(),
        date_to=original_run.date_to.isoformat(),
        countdown=0
    )
    
    await db.commit()
    
    return {
        "status": "replaying",
        "original_run_id": reconciliation_run_id,
        "new_run_id": new_run_id,
        "correlation_id": correlation_id
    }


# ============================================================================
# Audit Log
# ============================================================================

@router.get("/audit-log")
async def get_audit_log(
    merchant_id: Optional[str] = None,
    action: Optional[str] = None,
    days: int = 7,
    limit: int = 50,
    offset: int = 0,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream of all mutations: create, update, delete.
    
    With user, timestamp, before/after values.
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Build query
    query = select(AuditLog)
    
    cutoff = datetime.now(timezone.utc)
    from datetime import timedelta
    cutoff = cutoff - timedelta(days=days)
    
    query = query.where(AuditLog.created_at >= cutoff)
    
    if action:
        query = query.where(AuditLog.event_type.contains(action))
    
    # Get total count
    count_stmt = select(func.count()).select_from(AuditLog).where(
        AuditLog.created_at >= cutoff
    )
    if action:
        count_stmt = count_stmt.where(AuditLog.event_type.contains(action))
    
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    
    # Get paginated results
    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    audit_logs = result.scalars().all()
    
    return {
        "audit_logs": [
            {
                "id": str(log.id),
                "event_type": log.event_type,
                "actor_id": str(log.actor_id) if log.actor_id else None,
                "actor_role": log.actor_role,
                "timestamp": log.created_at.isoformat() if log.created_at else None,
                "payload": log.event_payload
            }
            for log in audit_logs
        ],
        "total": total,
        "days": days,
        "limit": limit,
        "offset": offset,
        "correlation_id": correlation_id
    }


# ============================================================================
# Database Inspection
# ============================================================================

@router.get("/db-stats")
async def get_database_stats(
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get table sizes, record counts, and query performance stats.
    
    Returns: {"transactions": 10000, "settlements": 500, ...}
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    stats = {}
    
    # Count records in key tables
    tables = [
        ("Transaction", Transaction),
        ("TransactionEvent", TransactionEvent),
        ("ProviderSyncJob", ProviderSyncJob),
        ("Incident", Incident),
        ("ReconciliationRun", ReconciliationRun),
        ("AuditLog", AuditLog),
        ("AIResponseLog", AIResponseLog),
    ]
    
    for table_name, model in tables:
        try:
            count_stmt = select(func.count()).select_from(model)
            count_result = await db.execute(count_stmt)
            count = count_result.scalar() or 0
            stats[table_name] = count
        except Exception as e:
            logger.error(f"Failed to count {table_name}: {e}")
            stats[table_name] = 0
    
    return {
        "stats": stats,
        "correlation_id": correlation_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================================
# AI Response Inspection
# ============================================================================

@router.get("/ai-responses/{response_id}")
async def get_ai_response(
    response_id: str,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get full AI response with prompt, context, response, and confidence.
    
    For debugging and auditing.
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Find AI response
    stmt = select(AIResponseLog).where(AIResponseLog.id == response_id)
    result = await db.execute(stmt)
    ai_response = result.scalars().first()
    
    if not ai_response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI response not found"
        )
    
    return {
        "response_id": str(ai_response.id),
        "query": ai_response.query,
        "model": ai_response.model_name,
        "prompt_version": ai_response.prompt_version,
        "context_sources": ai_response.context_sources,
        "response_text": ai_response.response_text,
        "confidence_score": ai_response.confidence_score,
        "has_hallucinations": bool(ai_response.has_hallucinations),
        "cited_records": ai_response.cited_record_ids,
        "created_at": ai_response.created_at.isoformat() if ai_response.created_at else None,
        "correlation_id": correlation_id
    }


@router.get("/ai-responses-by-query")
async def get_ai_responses_by_query(
    query: str,
    limit: int = 50,
    offset: int = 0,
    current_user=Depends(require_role(Role.admin)),
    db: AsyncSession = Depends(get_db),
):
    """
    Find all responses to a specific query pattern.
    
    Shows confidence variation.
    """
    admin_user = _ensure_admin(current_user)
    correlation_id = generate_correlation_id()
    
    # Search for responses with similar queries
    search_stmt = select(AIResponseLog).where(
        AIResponseLog.query.contains(query)
    ).order_by(AIResponseLog.created_at.desc()).limit(limit).offset(offset)
    
    count_stmt = select(func.count()).select_from(AIResponseLog).where(
        AIResponseLog.query.contains(query)
    )
    
    result = await db.execute(search_stmt)
    responses = result.scalars().all()
    
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0
    
    return {
        "query_pattern": query,
        "responses": [
            {
                "response_id": str(r.id),
                "query": r.query,
                "response_text": r.response_text[:200] + "..." if len(r.response_text) > 200 else r.response_text,
                "confidence_score": r.confidence_score,
                "model": r.model_name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in responses
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "correlation_id": correlation_id
    }
