# Async Job Architecture - Celery Integration

## Overview

BomiPay uses **Celery** with **Redis** as the message broker and result backend to handle asynchronous job processing. This architecture enables non-blocking execution of long-running operations like provider synchronization, reconciliation, and incident detection.

## Architecture Components

### 1. Message Broker & Result Backend
- **Redis** (`redis://localhost:6379/0`)
- Stores task messages and execution results
- High-performance, in-memory data store with disk persistence

### 2. Celery Worker
- Listens to Redis queue
- Executes tasks as they arrive
- Configured with concurrency of 4 workers
- Auto-retry on transient failures

### 3. Celery Beat Scheduler
- Periodic task orchestrator
- Runs on a schedule for health checks, reconciliation, and incident detection
- Synced with Redis for distributed deployments

### 4. Task Modules

#### Provider Sync Tasks (`src/bomipay/tasks/provider_sync.py`)
Synchronize transaction data from payment providers:
- `sync_provider_transactions()` - Sync transaction records
- `sync_provider_settlements()` - Sync settlement data
- `sync_provider_transfers()` - Sync transfer records
- `sync_provider_refunds()` - Sync refund records

**Retry Strategy:** Exponential backoff up to 3 retries
**Time Limit:** 30 minutes soft limit, 25 minutes hard limit

#### Webhook Processing Tasks (`src/bomipay/tasks/webhook_processing.py`)
Asynchronous webhook enrichment and aggregation:
- `post_process_webhook()` - Enrich webhook event after initial processing
- `aggregate_webhook_events()` - Group related webhooks into alerts

**Execution:** 1 second delay after webhook receipt
**Idempotency:** Provider event IDs prevent duplicate processing

#### Reconciliation Tasks (`src/bomipay/tasks/reconciliation.py`)
Financial data reconciliation:
- `run_reconciliation()` - Execute reconciliation for date range
- `generate_reconciliation_report()` - Generate and export reports

**Retry Strategy:** Automatic retry on failure
**Isolation:** Per-merchant with multi-tenancy safeguards

#### AI Insight Tasks (`src/bomipay/tasks/ai_insight.py`)
Machine learning-driven insights:
- `generate_ai_insight()` - Generate money-at-risk, incident analysis
- `cache_ai_responses()` - Pre-compute top queries

**Caching:** 1-hour TTL for insight results
**Cost Optimization:** Batch queries per merchant

#### Incident Detection (`src/bomipay/tasks/incident_generation.py`)
Automated incident creation from alerts:
- `detect_and_create_incidents()` - Correlate alerts into incidents

**Correlation:** Groups related alerts by merchant and time window
**Severity:** Auto-escalation based on alert counts

#### Alert Aggregation (`src/bomipay/tasks/alert_aggregation.py`)
Alert management and notifications:
- `aggregate_alerts()` - Suppress duplicates, escalate severity
- `send_alert_notification()` - Send via webhook/email/SMS

**Frequency:** Every 5 minutes per merchant
**Suppression:** Duplicate windows of 24 hours

#### Provider Health Monitoring (`src/bomipay/tasks/provider_health.py`)
Provider uptime and reliability:
- `poll_provider_health()` - Query provider status endpoints
- `calculate_provider_reliability_scores()` - Update metrics

**Frequency:** Hourly health polls
**Schedule:** Daily score recalculation at 00:00 UTC

#### Export Tasks (`src/bomipay/tasks/exports.py`)
Background CSV generation:
- `export_transactions_csv()` - Generate transaction exports
- `export_settlements_csv()` - Generate settlement exports

**Retry Strategy:** Exponential backoff (3 retries)
**Storage:** File system or S3

### 5. Task Registry (`src/bomipay/tasks/registry.py`)
Centralized task discovery and management:
```python
TASK_REGISTRY = {
    "sync_provider_transactions": sync_provider_transactions,
    "post_process_webhook": post_process_webhook,
    ...
}
```

### 6. Task Enqueue Service (`src/bomipay/services/task_enqueue.py`)
Helper methods for enqueueing tasks with standard configurations:
```python
TaskEnqueueService.enqueue_provider_sync(merchant_id, provider_account_id)
TaskEnqueueService.enqueue_webhook_post_process(webhook_event_id)
TaskEnqueueService.enqueue_reconciliation(merchant_id, date_from, date_to)
```

## Task Lifecycle

1. **Enqueue**: Task submitted to Redis queue via `apply_async()`
2. **Worker Pickup**: Celery worker picks up task from queue
3. **Execution**: Task runs in worker process (potentially on different machine)
4. **Result Storage**: Result saved to Redis
5. **Retry Logic**: On failure, tasks with `autoretry_for` exceptions retry with exponential backoff
6. **Cleanup**: Results expire after 1 hour (configurable)

## Retry Strategy

### Exponential Backoff
```
Retry 1: 2^1 * base = 2 seconds
Retry 2: 2^2 * base = 4 seconds
Retry 3: 2^3 * base = 8 seconds (max 3600 seconds)
```

### Retryable Errors
- Timeout / Connection failures (network transient)
- Rate limiting (HTTP 429)
- Server errors (HTTP 5xx)

### Permanent Errors
- Authentication failures (HTTP 401/403)
- Not found (HTTP 404)
- Validation errors (HTTP 400)

## Multi-Tenancy & Security

### Data Isolation
- All tasks scoped to specific `merchant_id`
- SQL queries enforce merchant filtering
- Redis keys include merchant context
- No cross-tenant data access

### Correlation IDs
- Distributed tracing via `correlation_id`
- Linked in all logs for investigation
- Thread-safe context propagation

### Rate Limiting
- Per-merchant task submission caps
- Worker concurrency limits prevent resource exhaustion
- Soft/hard time limits prevent runaway tasks

## Periodic Task Schedule

### Every 5 minutes
- `aggregate_alerts` - Deduplicate and escalate alerts

### Every hour
- `poll_provider_health` - Check provider status

### Daily at 00:00 UTC
- `calculate_provider_reliability_scores` - Update provider metrics

## Monitoring & Observability

### Logging
All tasks emit structured JSON logs:
```json
{
  "logger": "bomipay",
  "level": "INFO",
  "event": "sync_provider_transactions.started",
  "merchant_id": "m123",
  "provider_account_id": "pa456",
  "task_id": "abc-def-ghi"
}
```

### Metrics
- Task execution time (histogram)
- Task success/failure rates
- Queue depth and worker utilization

### Dead-Letter Queue (DLQ)
Failed tasks after max retries:
1. Logged with full context
2. Stored in Redis with `dlq:` prefix
3. Manually inspectable and replayable
4. Alert sent to ops team

## Docker Deployment

### Worker Service
```yaml
worker:
  command: celery -A src.bomipay.worker app worker --loglevel=info --concurrency=4
  depends_on:
    - db
    - redis
```

### Beat Service
```yaml
beat:
  command: celery -A src.bomipay.worker app beat --loglevel=info
  depends_on:
    - db
    - redis
    - worker
```

## Testing

### Eager Mode
Tests configure Celery with `task_always_eager=True`:
- Tasks execute synchronously during testing
- No Redis dependency needed
- Deterministic test execution

### Idempotency Testing
All tasks must be idempotent:
```python
# Running twice = same result
result1 = sync_provider_transactions(merchant_id, provider_id)
result2 = sync_provider_transactions(merchant_id, provider_id)
assert result1 == result2
```

## Best Practices

1. **Always Make Tasks Idempotent** - Safe to retry without side effects
2. **Use Correlation IDs** - Trace requests across services
3. **Set Appropriate Time Limits** - Prevent resource leaks
4. **Log Failures with Context** - Helps debugging
5. **Handle Partial Failures** - Don't assume all operations succeed
6. **Version Task Signatures** - Support rolling updates
7. **Monitor Queue Depth** - Alert on backlog buildup
8. **Test Retry Logic** - Verify exponential backoff

## Configuration Reference

### src/bomipay/worker.py
```python
app = Celery(
    "bomipay",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

app.conf.update(
    result_expires=3600,              # 1 hour
    task_track_started=True,
    task_time_limit=30 * 60,          # 30 minutes hard limit
    task_soft_time_limit=25 * 60,     # 25 minutes soft limit
    task_acks_late=True,              # ACK after completion
    worker_prefetch_multiplier=1,     # One task at a time
)
```

## Troubleshooting

### Worker Not Processing Tasks
1. Check Redis connectivity: `redis-cli ping`
2. Verify worker is running: `celery -A src.bomipay.worker app inspect active`
3. Check logs for import errors
4. Verify task registry is loaded

### Tasks Not Retrying
1. Confirm task has `autoretry_for` or explicit `retry()` call
2. Check `max_retries` configuration
3. Verify exception type matches retry conditions

### High Queue Depth
1. Increase worker concurrency
2. Split into multiple task types
3. Add more workers/machines
4. Optimize task execution time

### Results Not Persisting
1. Verify Redis backend is running
2. Check `result_expires` TTL configuration
3. Monitor Redis memory usage

## See Also
- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/documentation)
- [src/bomipay/worker.py](../worker.py) - Celery configuration
- [src/bomipay/tasks/](../tasks/) - Task definitions
- [tests/test_async_jobs.py](../../tests/test_async_jobs.py) - Test suite
