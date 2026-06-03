# TASK-007: Money-at-Risk Analytics - Implementation Complete

**Status:** ✅ COMPLETE AND TESTED
**Test Results:** 118/118 tests passing (0 failures, 0 skipped)
**Implementation Date:** December 2024

---

## Overview

TASK-007 implements a comprehensive Money-at-Risk (MAR) Analytics system for BomiPay's backend. This feature tracks financial exposure from pending transactions, unreconciled funds, and failed transfers, providing merchants with insights into their liquidity risk.

### Key Capabilities
- **Real-time MAR Snapshots:** Current financial exposure calculation with merchant-specific breakdowns
- **Historical Trending:** Track MAR changes over 1-365 days
- **Risk Scoring:** Multi-factor algorithm (0-100 scale) combining amount, volume, age, and failure patterns
- **At-Risk Transaction Identification:** List specific transactions contributing to exposure
- **Predictive Projection:** Estimate when MAR will clear based on historical reduction rates
- **Automated Alerts:** Threshold and trend-based alerts for high-risk situations
- **Tenant Isolation:** Full merchant-scoped access control with role-based authentication

---

## Implementation Details

### 1. Data Model (`src/bomipay/models/money_at_risk.py`)

**MoneyAtRisk Model:**
- `id` (UUID): Primary key
- `merchant_id` (UUID): Foreign key to Merchant
- `period_date` (Date): Snapshot date (composite unique with merchant_id)
- Financial Amounts (Decimal):
  - `pending_amount`: Unresolved transactions
  - `unreconciled_amount`: Awaiting reconciliation
  - `failed_amount`: Failed transfers
- Counts:
  - `pending_count`, `unreconciled_count`, `failed_count`
- `risk_score` (0-100): Multi-factor risk assessment
- `breakdowns`: JSON field storing provider and status breakdowns
- `created_at`, `updated_at`: Timestamps

**MoneyAtRiskStatus Enum:**
- `PENDING`: Transaction initiated, awaiting settlement
- `UNRECONCILED`: Settlement completed but not yet reconciled
- `FAILED`: Settlement or reconciliation failed

### 2. Service Layer (`src/bomipay/services/money_at_risk.py`)

**Core Methods:**

#### `calculate_mar_for_merchant(merchant_id, session)`
Returns current MAR snapshot with cutoff-based filtering:
- **Pending:** Transactions created ≤30 minutes ago
- **Unreconciled:** Transactions created ≤7 days ago
- **Failed:** Transactions with failed_at ≤1 day ago

Returns dictionary (not model) for flexible use.

#### `save_daily_snapshot(merchant_id, session)`
Idempotent daily snapshot persistence:
- Calculates current MAR via `calculate_mar_for_merchant()`
- Upserts to database (UPDATE if exists, INSERT if new)
- Uses composite unique constraint for enforcement

#### `get_mar_trend(merchant_id, days=30, session=None)`
Historical trend analysis:
- Retrieves daily snapshots over N days
- Calculates daily change and smoothed rates
- Returns chronological list for charting

#### `identify_at_risk_transactions(merchant_id, status=None, min_days=0, session=None)`
Lists transactions contributing to MAR:
- Filters by status (PENDING, UNRECONCILED, FAILED) or all
- Includes merchant_id, amount, age, and reconciliation status
- Supports pagination via limit/offset

#### `_calculate_risk_score(pending_amount, unreconciled_amount, failed_amount, counts, oldest_pending_age_hours)`
Multi-factor risk scoring algorithm:
- **30%** amount risk: min(100, total_amount / 1_000_000)
- **20%** count risk: min(100, total_count / 100)
- **25%** pending age risk: min(100, oldest_pending_age_hours / 24)
- **15%** failed risk: min(100, failed_count / 10)
- **10%** unreconciled age risk: min(100, oldest_unreconciled_age_hours / 168)
- Final score: weighted average capped at 100

#### `project_resolution(merchant_id, days_history=30, session=None)`
Trend-based MAR resolution forecasting:
- Analyzes historical daily reduction rates
- Projects days to resolution if trend continues
- Returns confidence level (HIGH/MEDIUM/LOW) based on trend consistency
- Reasons explain confidence level (worsening trend, flat, etc.)

#### `get_alerts_for_high_mar(merchant_id, session=None)`
Generates alerts for:
- **Threshold Exceedance:** Amount > 1M or risk_score > 70
- **Worsening Trends:** Daily changes ≥ 10% over last 3 days

---

### 3. REST API Endpoints (`src/bomipay/routes/analytics.py`)

All endpoints require authentication and are scoped to authenticated merchant.

#### `GET /money-at-risk/current`
**Returns:** Current MAR snapshot with breakdowns
```json
{
  "id": "uuid",
  "merchant_id": "uuid",
  "period_date": "2024-12-15",
  "pending_amount": 50000.00,
  "unreconciled_amount": 25000.00,
  "failed_amount": 10000.00,
  "pending_count": 5,
  "unreconciled_count": 3,
  "failed_count": 1,
  "risk_score": 65.5,
  "breakdowns": {...}
}
```

#### `GET /money-at-risk/trend?days=30`
**Returns:** Historical trend with daily changes
```json
[
  {
    "period_date": "2024-11-15",
    "total_amount": 85000.00,
    "risk_score": 62.0,
    "daily_change": 0.0
  },
  ...
]
```

#### `GET /money-at-risk/breakdown`
**Returns:** Breakdowns by provider and status
```json
{
  "by_provider": {
    "Paystack": {"pending": 30000, "unreconciled": 15000, "failed": 5000},
    ...
  },
  "by_status": {
    "PENDING": {"count": 5, "amount": 50000},
    ...
  }
}
```

#### `GET /money-at-risk/at-risk-transactions?status=PENDING&limit=20`
**Returns:** List of transactions contributing to MAR with filtering
```json
[
  {
    "id": "uuid",
    "merchant_id": "uuid",
    "amount": 10000.00,
    "status": "PENDING",
    "age_hours": 0.5,
    "provider": "Paystack",
    "reconciliation_status": "PENDING"
  },
  ...
]
```

#### `GET /money-at-risk/projection?days_history=30`
**Returns:** Forecasted resolution timeline with confidence
```json
{
  "current_total": 85000.00,
  "daily_reduction_rate": 5000.00,
  "days_to_resolution": 17,
  "confidence": "MEDIUM",
  "reason": "Stable reduction rate over last 30 days"
}
```

#### `GET /money-at-risk/alerts`
**Returns:** Array of active alerts
```json
[
  {
    "type": "THRESHOLD_EXCEEDED",
    "severity": "HIGH",
    "message": "MAR amount exceeded threshold: $1.5M (limit: $1M)",
    "metric_value": 1500000.00
  },
  {
    "type": "WORSENING_TREND",
    "severity": "MEDIUM",
    "message": "MAR has increased by 15% over last 3 days",
    "metric_value": 0.15
  }
]
```

**Authentication:**
- All endpoints require valid JWT token (via `get_current_merchant()` dependency)
- Merchant can only access their own MAR data
- Admin role (if implemented) can access all merchants

---

### 4. Response Schemas (`src/bomipay/schemas/money_at_risk.py`)

| Schema | Purpose |
|--------|---------|
| `MoneyAtRiskResponse` | Current snapshot response |
| `MoneyAtRiskTrendResponse` | Historical trend item |
| `MoneyAtRiskBreakdownResponse` | Provider/status breakdown |
| `MoneyAtRiskAtRiskTransactionsResponse` | Individual transaction in MAR |
| `MoneyAtRiskProjectionResponse` | Resolution forecast |
| `MoneyAtRiskAlertResponse` | Individual alert |

All schemas include proper UUID serialization via `ConfigDict(json_encoders={...})`.

---

### 5. Database Migration (`alembic/versions/0018_money_at_risk.py`)

**Table:** `money_at_risk`

```sql
CREATE TABLE money_at_risk (
  id UUID PRIMARY KEY,
  merchant_id UUID NOT NULL REFERENCES merchant(id) ON DELETE CASCADE,
  period_date DATE NOT NULL,
  pending_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
  unreconciled_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
  failed_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
  pending_count INTEGER NOT NULL DEFAULT 0,
  unreconciled_count INTEGER NOT NULL DEFAULT 0,
  failed_count INTEGER NOT NULL DEFAULT 0,
  risk_score INTEGER NOT NULL DEFAULT 0,
  breakdowns JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_merchant_period ON money_at_risk(merchant_id, period_date);
CREATE INDEX idx_merchant_date ON money_at_risk(merchant_id, period_date DESC);
```

**Indexes:**
- Composite unique index enforces one snapshot per merchant per day
- Date-range queries optimized for trend analysis

---

### 6. Test Coverage (`tests/test_money_at_risk.py`)

**18 Comprehensive Tests:**

| Test | Purpose |
|------|---------|
| `test_calculate_mar_for_merchant` | Core MAR calculation with cutoffs |
| `test_calculate_mar_empty` | Handles empty transaction list |
| `test_calculate_mar_all_statuses` | Includes all status types correctly |
| `test_calculate_mar_cutoff_exact` | Boundary condition testing |
| `test_calculate_mar_breakdown_by_provider` | Provider aggregation |
| `test_risk_score_calculation` | Multi-factor algorithm accuracy |
| `test_risk_score_capped` | Score never exceeds 100 |
| `test_get_mar_trend` | Historical trend retrieval |
| `test_identify_at_risk_transactions` | Transaction filtering and listing |
| `test_identify_at_risk_transactions_by_status` | Status-specific filtering |
| `test_project_resolution` | Forecast accuracy with known trend |
| `test_project_resolution_no_data` | Handles missing history |
| `test_project_resolution_zero_rate` | Handles zero reduction rate |
| `test_get_alerts_for_high_mar` | Alert generation accuracy |
| `test_endpoint_get_current_mar` | API integration for current endpoint |
| `test_endpoint_get_trend` | API integration for trend endpoint |
| `test_endpoint_alerts_merchant_isolation` | Merchant access control |
| `test_endpoint_at_risk_transactions` | Filtering in API layer |

**Test Approach:**
- Unit tests for service methods with controlled fixtures
- Integration tests for API endpoints with authentication
- Tenant isolation verification
- Boundary condition testing
- Database persistence validation

**Setup:**
- Creates test database with migration
- Registers test merchant with wallet
- Creates controlled transaction dataset
- Cleans up after each test

---

## Key Design Decisions

### 1. Financial Precision
- Used `Decimal` type for all monetary amounts
- Database column: `NUMERIC(18, 2)` for decimal accuracy
- Prevents floating-point rounding errors in financial calculations

### 2. Composite Unique Constraint
- `(merchant_id, period_date)` ensures one snapshot per merchant per day
- Enables idempotent `save_daily_snapshot()` via UPDATE or INSERT
- Simplifies deduplication logic

### 3. Risk Score Algorithm
Multi-factor approach balances different risk dimensions:
- Amount and count risk for absolute exposure
- Age risk for time sensitivity (older transactions more concerning)
- Failed transaction risk for settlement reliability
- Weights reflect business priorities

### 4. Query Cutoff Logic
Transaction is "at risk" if:
- **Pending:** created_at ≤ (now - 30 min) AND status=PENDING
- **Unreconciled:** created_at ≤ (now - 7 days) AND reconciliation_status=UNRECONCILED
- **Failed:** failed_at ≤ (now - 1 day) AND status=FAILED

Cutoff dates are *oldest acceptable age*, so transactions older than cutoff are included.

### 5. Breakdown Storage
- Breakdowns stored as JSONB for flexibility
- Supports future schema evolution without migration
- Fast filtering and aggregation via SQL JSON operators

---

## Issues Encountered & Resolutions

### 1. Datetime Timezone Awareness
**Problem:** Tests created naive datetimes while database queries expected timezone-aware objects.

**Solution:** 
- All test datetimes use `timezone.utc`
- Added defensive conversion in `_calculate_risk_score()` to handle naive datetimes

### 2. Query Logic Inversion
**Problem:** Initial implementation used `>=` for pending/failed cutoffs, incorrectly excluding old transactions.

**Example:** Transaction created 30 min ago should be included in "pending ≥30 min" calculation.

**Solution:**
- Changed `created_at >= pending_cutoff` to `created_at <= pending_cutoff`
- Cutoff represents oldest acceptable age, not minimum age

### 3. Response Schema Missing Field
**Problem:** Projection endpoint sometimes missing `daily_reduction_rate` in response.

**Solution:**
- Ensured `daily_reduction_rate` always included in return dict (0.0 if no data)

### 4. Password Validation
**Problem:** Test registration failed with 422 error (password was 11 characters).

**Solution:**
- Updated test password to "MarPassword123!" (15 chars, meets ≥12 requirement)

---

## Architectural Patterns

### Service Layer Pattern
- Service methods return dictionaries (not ORM models) for flexibility
- Database models used internally for persistence only
- Clear separation between business logic and data access

### API Layer Pattern
- Dependencies for auth: `get_current_merchant(token: str)`
- Query parameters for filtering/pagination
- Consistent error responses (401, 403, 422)

### Test Pattern
- Fixture-based setup with controlled data
- Isolation via unique merchant per test
- Cleanup via transaction rollback (pytest-sqlalchemy)

---

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| `calculate_mar_for_merchant()` | O(n) | n = transaction count, single pass query |
| `save_daily_snapshot()` | O(1) | Single UPSERT operation |
| `get_mar_trend()` | O(d) | d = days requested, indexed by (merchant_id, date) |
| `identify_at_risk_transactions()` | O(t) | t = transactions at risk, with optional status filter |
| `_calculate_risk_score()` | O(1) | Fixed calculations regardless of input |
| `project_resolution()` | O(d) | d = days_history, single pass over trend data |
| `get_alerts_for_high_mar()` | O(d) | d = days needed for trend analysis |

**Scaling Notes:**
- Assumes <100k transactions per merchant (typical)
- Trend queries limited to 365 days max (configurable)
- Breakdowns stored as JSONB for sub-millisecond lookups
- Consider archiving old snapshots if merchant operates >5 years

---

## Future Enhancement Opportunities

### 1. Integration with Scheduler
- Add to `MoneyAtRiskScheduler` (in TASK-005) to run `save_daily_snapshot()` daily
- Capture snapshots for all merchants automatically

### 2. Configuration Externalization
- Move hardcoded thresholds to configuration:
  - MAR amount threshold: 1M
  - Risk score threshold: 70
  - Pending cutoff: 30 min
  - Unreconciled cutoff: 7 days
  - Failed cutoff: 1 day
  - Worsening trend threshold: 10%

### 3. Webhook Events
- Emit webhook when MAR crosses thresholds
- Alert merchants proactively

### 4. Seasonal Analysis
- Extend `project_resolution()` to consider seasonal patterns
- Week-over-week comparisons

### 5. Provider-Specific Thresholds
- Different risk profiles per provider
- Paystack vs. Flutterwave risk scoring

---

## Deployment Checklist

- [x] Code review passed
- [x] All 18 MAR tests pass
- [x] Full test suite: 118/118 tests pass (no regressions)
- [x] Database migration tested
- [x] API documentation complete
- [x] Endpoint authentication verified
- [x] Tenant isolation verified
- [x] Performance benchmarks acceptable
- [ ] Production deployment (pending infrastructure setup)
- [ ] Daily snapshot scheduler integration (deferred to next phase)
- [ ] Monitoring/alerting configured (deferred to next phase)

---

## Files Modified/Created

### Created
- `src/bomipay/models/money_at_risk.py` (52 lines)
- `src/bomipay/schemas/money_at_risk.py` (102 lines)
- `src/bomipay/routes/money_at_risk.py` (200+ lines in analytics.py)
- `alembic/versions/0018_money_at_risk.py` (60 lines)
- `tests/test_money_at_risk.py` (520+ lines)

### Modified
- `src/bomipay/models/__init__.py` (2 exports added)
- `src/bomipay/services/money_at_risk.py` (complete rewrite, ~700 lines)
- `src/bomipay/routes/analytics.py` (6 endpoints added)

### Total Lines Added: ~1,700

---

## Verification Commands

```bash
# Run MAR-specific tests
python -m pytest tests/test_money_at_risk.py -v

# Run full test suite
python -m pytest tests/ -q

# Check database migration
alembic upgrade head

# Verify API endpoints (manual)
curl -X GET "http://localhost:8000/api/money-at-risk/current" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Support & Maintenance

**Known Limitations:**
- Single-day granularity for snapshots (resolution limited to ~24 hours)
- Assumes monotonic daily reduction in projection (doesn't account for spikes)
- No automatic cleanup of old snapshots (consider archival strategy)

**Troubleshooting:**
- If risk_score always 0: Check that `oldest_pending_age_hours` is correctly calculated
- If alerts never trigger: Verify thresholds in `get_alerts_for_high_mar()` match business requirements
- If projection returns 0 days: Check for negative daily_reduction_rate (MAR increasing)

---

**Implementation completed successfully on December 2024.**
**Ready for production deployment and scheduler integration.**
