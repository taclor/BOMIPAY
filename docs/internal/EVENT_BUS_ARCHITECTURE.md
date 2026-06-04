# Event Bus Architecture

## Overview

The Event Bus is a foundational system for Bomi Pay that enables asynchronous event-driven communication across services. It uses **Redis Streams** for message durability and **domain events** persisted to the database for full audit trail and replay capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Domain Services                          │
│  (Transaction, Incident, Settlement, Alert, etc.)          │
└───────────┬─────────────────────────────────────────────────┘
            │
            │ EventPublisher.publish_event()
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Event Publisher Service                     │
│  1. Store in domain_events table (append-only)              │
│  2. Publish to Redis Streams (bomipay.events)               │
│  3. Check for idempotency (correlation_id)                  │
└───────────┬───────────────────────────────────────────────┬─┘
            │                                               │
     ┌──────▼─────────────────────────────────────────────┬▼──────┐
     │           PostgreSQL (domain_events)      │    Redis Streams  │
     │  ┌─────────────────────────────────────┐  │ (bomipay.events)  │
     │  │ id (GUID)                           │  │ ┌───────────────┐ │
     │  │ event_type (indexed)                │  │ │ Consumer Group│ │
     │  │ merchant_id (indexed)               │  │ │  bomi-pay-   │ │
     │  │ aggregate_id (indexed)              │  │ │ processors    │ │
     │  │ aggregate_type                      │  │ └───────────────┘ │
     │  │ correlation_id (indexed, unique)    │  │                   │
     │  │ request_id                          │  │ Retention: 24h    │
     │  │ payload_json                        │  │ Approximate: True │
     │  │ published_at                        │  │                   │
     │  │ created_at (append-only)            │  │                   │
     │  └─────────────────────────────────────┘  │                   │
     └────────────────────────────────────────────┴───────────────────┘
            │
            │ EventProcessor.consume_events()
            │ (Celery beat task every 10 seconds)
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│               Event Processor Service                         │
│  1. Read from Redis Streams consumer group                  │
│  2. Deserialize event payload                              │
│  3. Dispatch to appropriate handler                        │
│  4. ACK message (mark processed)                           │
└───────────┬─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│               Event Handlers (16+ types)                     │
│                                                              │
│  - transaction.created                                      │
│  - transaction.updated                                      │
│  - transaction.settled                                      │
│  - settlement.received                                      │
│  - settlement.mismatch_detected                            │
│  - reconciliation.completed                                │
│  - reconciliation.mismatch                                 │
│  - incident.created                                        │
│  - incident.acknowledged                                   │
│  - incident.resolved                                       │
│  - alert.created                                           │
│  - alert.resolved                                          │
│  - dispute.created                                         │
│  - provider.sync.completed                                 │
│  - provider.sync.failed                                    │
│  - webhook.received                                        │
│  - webhook.processed                                       │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Event Model (`models/event.py`)

Defines the domain event structure and event types.

```python
class EventType(str, enum.Enum):
    transaction_created = "transaction.created"
    # ... 15 more event types

class DomainEvent(Base):
    id: GUID (primary key)
    event_type: str (indexed)
    merchant_id: GUID (indexed)
    aggregate_id: str (indexed)
    aggregate_type: str
    correlation_id: str (indexed, unique per request)
    request_id: str
    payload_json: str (full event payload)
    published_at: datetime
    created_at: datetime (append-only)
```

**Storage**: PostgreSQL table `domain_events` with composite indexes for efficient queries.

### 2. Event Publisher (`services/event_publisher.py`)

Publishes events to both database and Redis Streams.

```python
event = await EventPublisher.publish_event(
    db=db,
    event_type=EventType.transaction_created,
    merchant_id=str(merchant_id),
    aggregate_id=str(transaction_id),
    aggregate_type="transaction",
    payload={"amount": 1000, "currency": "USD"},
    correlation_id=request_id,  # Optional, auto-generated if not provided
)
```

**Flow**:
1. Create `DomainEvent` object
2. Store in PostgreSQL (flush to ensure durability)
3. Publish to Redis Streams
4. Return persisted event object

**Idempotency**: Use `correlation_id` to prevent duplicate events.

### 3. Event Processor (`services/event_processor.py`)

Consumes events from Redis Streams and dispatches to handlers.

**Consumer Group Model**:
- Stream: `bomipay.events`
- Consumer Group: `bomi-pay-processors`
- Consumer: `processor-1`
- ACK: Events are acknowledged after successful processing

**Flow**:
1. Read pending messages from stream (`XREADGROUP`)
2. For each message:
   - Deserialize payload
   - Look up handler by event type
   - Call handler with payload
   - ACK message (mark processed)

**Error Handling**:
- Failed events remain pending (can be retried)
- Errors logged with full context
- Never ACKs failed events

### 4. Event Handlers (`services/event_handlers.py`)

Process specific event types. Each handler is idempotent and handles business logic.

```python
@staticmethod
async def handle_transaction_created(payload: dict):
    # Trigger reconciliation check
    # Update dashboard cache
    # Notify merchant webhook
```

**Event Types** (16 handlers):
- `transaction.*`: Track transaction lifecycle
- `settlement.*`: Track settlement and reconciliation
- `reconciliation.*`: Update dashboard and metrics
- `incident.*`: Manage operational incidents
- `alert.*`: Process alert notifications
- `dispute.*`: Handle disputed transactions
- `provider.*`: Sync provider data
- `webhook.*`: Process incoming webhooks

### 5. Redis Streams Manager (`observability/streams.py`)

Manages stream initialization and monitoring.

```python
# Initialize streams and consumer groups
await EventStreamManager.setup_event_streams()

# Get stream info
info = await EventStreamManager.get_stream_info()
# Returns: {stream, length, consumer_groups, etc.}

# Reset consumer group (replay from beginning)
await EventStreamManager.reset_consumer_group(
    stream_name="bomipay.events",
    consumer_group="bomi-pay-processors",
    start_id="0"  # "0" = from beginning, "$" = from end
)

# Get pending messages
pending = await EventStreamManager.get_pending_messages()
```

### 6. Event Replay (`services/event_replay.py`)

Replay events for debugging, recovery, or testing.

```python
# Replay all events for a merchant
count = await EventReplayer.replay_events_for_merchant(
    db=db,
    merchant_id=str(merchant_id),
    event_types=["transaction.created", "transaction.settled"]  # Optional
)

# Replay events since a timestamp
count = await EventReplayer.replay_since_timestamp(
    db=db,
    since=datetime.now() - timedelta(hours=1)
)

# Replay events for a specific aggregate
count = await EventReplayer.replay_events_for_aggregate(
    db=db,
    aggregate_type="transaction",
    aggregate_id=str(transaction_id)
)

# Get events for debugging
events = await EventReplayer.get_events_for_merchant(
    db=db,
    merchant_id=str(merchant_id),
    limit=100
)
```

### 7. Celery Task (`tasks/event_consumption.py`)

Periodic task that consumes events every 10 seconds.

```python
@app.task
def consume_and_process_events(self):
    asyncio.run(EventProcessor.consume_events(block_once=True))
```

**Celery Beat Schedule**:
```python
"consume-events-every-10-seconds": {
    "task": "bomipay.tasks.event_consumption.consume_and_process_events",
    "schedule": 10.0,
}
```

## Event Flow Examples

### Example 1: Transaction Created

```
1. TransactionService.create_transaction()
   └─> EventPublisher.publish_event(EventType.transaction_created, ...)

2. Event stored in domain_events table
   └─> Payload: {transaction_id, merchant_id, amount, currency, ...}

3. Published to Redis Stream: bomipay.events
   └─> Message: {event_type, merchant_id, aggregate_id, payload, ...}

4. Celery beat task runs every 10 seconds
   └─> EventProcessor.consume_events(block_once=True)

5. EventProcessor reads from consumer group
   └─> EventHandlers.handle_transaction_created(payload)

6. Handler processes event:
   - Trigger reconciliation check
   - Update dashboard cache
   - Notify merchant webhook
```

### Example 2: Event Replay for Recovery

```
1. Service restart or recovery needed

2. Admin calls EventReplayer:
   await EventReplayer.replay_events_for_merchant(
       db=db,
       merchant_id=str(merchant_id),
       since=datetime.now() - timedelta(hours=1)
   )

3. EventReplayer queries domain_events table
   └─> Filter by merchant_id and created_at >= since

4. For each event:
   - Deserialize payload
   - Call appropriate handler
   - Handler re-processes business logic
```

## Correlation IDs

**Purpose**: Track a request through entire event chain for debugging and monitoring.

**Usage**:
```python
# In API route
correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

# When publishing event
event = await EventPublisher.publish_event(
    ...,
    correlation_id=correlation_id,
    request_id=request.id
)

# In logs, correlation_id appears in all related events
logger.info("Event published", extra={"correlation_id": correlation_id})
```

**Propagation**:
- From API request to event publisher
- Stored in domain_events table
- Included in Redis Stream message
- Available in event handlers for logging

## Idempotency

**Problem**: Same event shouldn't be published twice (network retries, etc.).

**Solution**: Use `correlation_id` as unique constraint.

```python
# Check if event already published
exists = await EventPublisher.check_event_exists(db, correlation_id)
if not exists:
    event = await EventPublisher.publish_event(..., correlation_id=correlation_id)
```

**Database Constraint**: Index on `correlation_id` ensures uniqueness at application level.

## Performance Considerations

### Database Indexing
- `event_type`: Query events by type
- `merchant_id`: Query events by merchant
- `aggregate_id`: Query events by aggregate
- `correlation_id`: Check idempotency, trace requests
- `published_at`: Query recent events
- Composite indexes: `(merchant_id, event_type)`, `(aggregate_type, aggregate_id)`

### Redis Streams Configuration
- **Retention**: 24 hours (configurable)
- **Approximate**: True (faster trimming)
- **Consumer Group**: Tracks consumer progress (can resume from last ACK)

### Processing
- **Batch Size**: 10 messages per XREADGROUP
- **Block Duration**: 1000ms (1 second)
- **Celery Frequency**: Every 10 seconds
- **Maximum throughput**: ~100 events/second at scale

## Debugging and Monitoring

### Get Stream Status
```python
info = await EventStreamManager.get_stream_info()
# {
#   "stream": "bomipay.events",
#   "length": 1250,
#   "first_entry_id": "1234567890000-0",
#   "last_entry_id": "1234567891234-5",
#   "consumer_groups": [
#     {
#       "name": "bomi-pay-processors",
#       "consumers": 1,
#       "pending": 0
#     }
#   ]
# }
```

### Get Pending Messages
```python
pending = await EventStreamManager.get_pending_messages()
# Pending messages are unacked, waiting to be retried
```

### View Events for a Merchant
```python
events = await EventReplayer.get_events_for_merchant(
    db=db,
    merchant_id=str(merchant_id),
    limit=100
)
# Returns list of events for debugging
```

### Reset Consumer Group (Replay)
```python
await EventStreamManager.reset_consumer_group(
    stream_name="bomipay.events",
    consumer_group="bomi-pay-processors",
    start_id="0"  # Replay from beginning
)
```

## Production Deployment

### Pre-Deployment Checklist
- [ ] Database migration applied (`alembic upgrade head`)
- [ ] Redis is running and accessible
- [ ] Celery worker configured to run event consumption task
- [ ] Event stream initialized via setup task or admin UI
- [ ] Log aggregation configured for event traces

### Initialization
```python
# One-time setup
await EventStreamManager.setup_event_streams()
```

### Monitoring
- Monitor Celery task execution time
- Track Redis Stream length (should not grow unbounded)
- Monitor consumer group pending count (should be 0)
- Set alerts on handler errors

### Scaling
- Add multiple consumer instances for parallel processing
- Each instance consumes different messages from same group
- Redis Streams handles distribution automatically

## Testing

### Unit Tests
```python
# Test event publishing
event = await EventPublisher.publish_event(db, event_type, ...)
assert event.id is not None
assert event.correlation_id is not None

# Test handler dispatch
await EventHandlers.handle_event(event_type, payload)

# Test event replay
count = await EventReplayer.replay_events_for_merchant(db, merchant_id)
assert count > 0
```

### Integration Tests
```python
# End-to-end: publish -> stream -> consume -> handle
event = await EventPublisher.publish_event(...)  # Stores in DB
# Verify in Redis Stream
messages = redis.xread({STREAM_NAME: "0"})
assert len(messages) > 0
```

### Debugging Tests
```python
# Check event exists (idempotency)
exists = await EventPublisher.check_event_exists(db, correlation_id)

# Replay and verify
count = await EventReplayer.replay_events_for_merchant(db, merchant_id)
```

## Troubleshooting

### Events not being processed
1. Check Celery worker is running: `celery -A bomipay.worker worker --beat`
2. Check Redis connection: `redis-cli ping`
3. Check consumer group pending messages: `get_pending_messages_task()`
4. Check logs for handler errors

### Redis Stream growing unbounded
1. Check consumer group is ACKing: `xinfo groups bomipay.events`
2. Check for failed handlers: look for exceptions in logs
3. Manually ACK pending messages if safe: `xack bomipay.events bomi-pay-processors <id>`
4. Reset consumer group to latest: `reset_consumer_group("0", "$")`

### Duplicate events
1. Check if correlation_id is being used
2. Verify idempotency check: `check_event_exists(db, correlation_id)`
3. Look for multiple publishes with same correlation_id

### Handler failures
1. Check handler implementation for exceptions
2. Review handler logs with correlation_id
3. Replay events if needed: `replay_events_for_merchant(db, merchant_id)`

## Migration Path (TASK-003 to Production)

### Phase 1: Foundation (Current)
- Event model + migration
- Publisher, processor, handlers
- Redis streams setup
- Tests

### Phase 2: Integration (Next Tasks)
- Emit events from existing services (TransactionService, IncidentService, etc.)
- Add event handlers for business logic
- Implement webhooks from event stream

### Phase 3: Production
- Monitor event processing latency
- Scale consumer group if needed
- Archive old events from domain_events table
- Implement event schema versioning

## API Examples

### Publish an Event
```python
from src.bomipay.services.event_publisher import EventPublisher
from src.bomipay.models.event import EventType

event = await EventPublisher.publish_event(
    db=db,
    event_type=EventType.transaction_created,
    merchant_id=str(merchant_id),
    aggregate_id=str(transaction_id),
    aggregate_type="transaction",
    payload={
        "amount": 100000,
        "currency": "NGN",
        "provider": "paystack",
        "status": "success",
    },
    correlation_id=str(request_id),
)
```

### Listen to Events (Streaming)
```python
from src.bomipay.services.event_processor import EventProcessor

# Start consuming (blocking)
await EventProcessor.consume_events(block_once=False)

# Or just process one batch
await EventProcessor.consume_events(block_once=True)
```

### Replay Events
```python
from src.bomipay.services.event_replay import EventReplayer

# Replay for merchant
count = await EventReplayer.replay_events_for_merchant(db, merchant_id)

# Replay for aggregate
count = await EventReplayer.replay_events_for_aggregate(
    db, "transaction", transaction_id
)

# Get events
events = await EventReplayer.get_events_for_merchant(db, merchant_id)
```

---

**Last Updated**: 2024-01-15
**Version**: 1.0
**Maintainer**: Bomi Pay Engineering
