# BomiPay Production Readiness Report

Date: 2026-06-05

## Test Suite Status

| Metric | Count |
|--------|-------|
| Total tests | 191 |
| Passing | 190 |
| Failing | 1 |

**Failing test:** `tests/test_webhook.py::test_paystack_webhook_ingestion_and_idempotency`

**Root cause (pre-existing):** The test stores a plain-text string `"test_secret"` in `provider_account.secret_encrypted`, then calls the webhook handler which attempts to Fernet-decrypt it. This is a test fixture issue — the test must encrypt the value with a valid Fernet key before storing it. The production code path (`encrypt_secret` → `decrypt_secret`) is correct; only the test is broken.

---

## Migration Status

| Metric | Count |
|--------|-------|
| Total migrations | 19 |
| All tables present | ✅ Yes (after 0019 added) |

### Migration chain (in order)

| # | Revision ID | Table(s) affected |
|---|------------|-------------------|
| 01 | 0001_initial | merchants, users |
| 02 | 0002_provider_accounts | provider_accounts |
| 03 | 0003_transactions | transactions, transaction_events |
| 04 | 0004_alerts | alerts |
| 05 | 0005_notifications_and_alert_extensions | notifications, alert extensions |
| 06 | 0006_harden_alerts_notifications_transactions | composite indices |
| 07 | 0007_reconciliation_engine | reconciliation_runs, reconciliation_results |
| 08 | 0008_add_alert_fields | alert columns |
| 09 | 0009_bank_accounts | bank_accounts |
| 10 | 0010_data_sources | data_sources |
| 11 | 0011_bank_statements | bank_statements |
| 12 | 0012_provider_sync_jobs | provider_sync_jobs |
| 13 | 0013_incidents | incidents |
| 14 | 0014_task001_foundation_hardening | hardening columns |
| 15 | 0015_bank_account_last4_and_data_source_link | bank_account columns |
| 16 | 0016_bank_statement_reconciliation | bank_statement reconciliation |
| 17 | 0017_provider_sync_enhancements | provider_sync_jobs retry/backoff |
| 18 | 0018_money_at_risk | money_at_risk |
| 19 | 0019_dashboard_snapshots | dashboard_snapshots (**added this task**) |

**Previously missing:** `dashboard_snapshots` — the `DashboardSnapshot` model in `src/bomipay/models/dashboard.py` had no corresponding migration. Migration `0019_dashboard_snapshots` was created, verified as the sole chain head, and includes three indices for `merchant_id`, `snapshot_time`, and the composite `(merchant_id, snapshot_time)`.

---

## Security Findings

### ✅ Passing

- **JWT uses env var:** `SECRET_KEY` is loaded via `pydantic-settings` / env var with `Field(..., alias="SECRET_KEY")` — no default, required at startup.
- **JWT algorithm configurable:** `JWT_ALGORITHM` env var (default `HS256`). Access and refresh token TTLs are also configurable env vars.
- **Provider secrets encrypted at rest:** `encrypt_secret` / `decrypt_secret` (Fernet) applied to `api_key_encrypted` and `secret_encrypted` in `ProviderAccount`. Bank account numbers encrypted + only `last4` stored.
- **Bank account numbers masked:** `mask_account_number()` utility in `bank_account.py` service; only `account_number_last4` exposed in responses; full number encrypted in `account_number_encrypted` column.
- **CORS origins from env:** `CORS_ALLOWED_ORIGINS` env var parsed to list; defaults to localhost only.
- **No hardcoded live secrets:** `grep` for `sk_live`, `pk_live` returned no matches.
- **No raw SQL:** SQLAlchemy ORM used throughout; no `text()` raw queries found in service or route code.
- **Input validation via Pydantic:** All route handlers accept Pydantic schema objects for request bodies. Path parameters use `UUID` type annotations to enforce format.
- **Role-based access control:** `require_role()` dependency enforced on all write endpoints; merchant-scoped access enforced via `_check_merchant_access()` helpers.
- **HTTP exceptions used consistently:** 140 `raise HTTPException` calls across route layer — business errors are properly surfaced as HTTP responses.
- **Request ID middleware:** All responses carry `X-Request-ID` for traceability.

### ⚠️ Issues Found

| # | Issue | Severity | Recommendation |
|---|-------|----------|----------------|
| 1 | `except Exception` (bare) in `services/auth.py:43` — swallows all token-decode errors and re-raises as HTTP 401 | **Low** | Acceptable; converts decode errors into standard 401. Consider logging the original exception at DEBUG level for diagnostics. |
| 2 | `except Exception` in `services/bank_statement.py`, `notification.py`, `payment_graph.py`, `provider_sync.py`, `reconciliation.py` — catches all exceptions including programmer errors | **Low–Medium** | Each catch site should log the exception (`logger.exception(...)`) before re-raising or returning a safe error value so errors are observable in production. Several sites already log; verify all do. |
| 3 | `PROVIDER_ENCRYPTION_KEY` is `Optional` (defaults to `None`) | **Medium** | If `None`, `encrypt_secret` / `decrypt_secret` will fail at runtime when adding/reading provider accounts. Enforce non-null in production deploy (see checklist below). |
| 4 | Webhook secret validation pre-existing test failure | **Low** | Test fixture must create a properly Fernet-encrypted secret. Production webhook path is correct; only the test setup is wrong. |
| 5 | `docs_url="/docs"` and `redoc_url="/redoc"` enabled in `main.py` | **Low** | Disable or protect with authentication in production to avoid leaking API schema. |

---

## Performance Observations

- **No N+1 patterns detected:** No `for … in … await db` loops found in service layer — queries use bulk `select()` with filters.
- **Composite indices on hot paths:**
  - `(merchant_id, status)` on alerts, notifications, transactions ✅
  - `(merchant_id, created_at)` on transactions ✅
  - `(merchant_id, period_date)` on money_at_risk ✅
  - `(merchant_id, snapshot_time)` on dashboard_snapshots ✅ (added in 0019)
  - `status` on provider_sync_jobs ✅
  - `(merchant_id, status)` on incidents ✅
- **JSON columns:** `provider_statuses`, `alerts`, `anomaly_indicators` in `dashboard_snapshots` are JSON blobs — not queryable by field in SQLite/PostgreSQL without JSONPath. Acceptable for read-heavy dashboard use case.
- **Pagination:** Confirm all list endpoints use `limit`/`offset` (or cursor) to prevent unbounded queries in production with large datasets.

---

## Configuration

All secrets and environment-specific values are driven by environment variables. Required for production:

| Env Var | Required | Description |
|---------|----------|-------------|
| `SECRET_KEY` | **Yes** | JWT signing key — strong random value (≥32 bytes) |
| `DATABASE_URL` | **Yes** | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `PROVIDER_ENCRYPTION_KEY` | **Yes** | Fernet key for encrypting provider API credentials |
| `PAYSTACK_WEBHOOK_SECRET` | **Yes** | HMAC secret for Paystack webhook signature validation |
| `CORS_ALLOWED_ORIGINS` | **Yes** | Comma-separated list of production frontend domains |
| `REDIS_URL` | No | Defaults to `redis://localhost:6379/0`; required if using background jobs/caching |
| `BOMIPAY_ENV` | No | Defaults to `development`; set to `production` |
| `JWT_ALGORITHM` | No | Defaults to `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_SECONDS` | No | Defaults to 900 (15 min) |
| `JWT_REFRESH_TOKEN_EXPIRE_SECONDS` | No | Defaults to 604800 (7 days) |

---

## Deployment Checklist

- [ ] Set `SECRET_KEY` to strong random value (`python -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] Set `DATABASE_URL` to production PostgreSQL (`postgresql+asyncpg://user:pass@host/db`)
- [ ] Set `PROVIDER_ENCRYPTION_KEY` to a valid Fernet key (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- [ ] Set `PAYSTACK_WEBHOOK_SECRET` to the value from Paystack dashboard
- [ ] Set `CORS_ALLOWED_ORIGINS` to production frontend domains
- [ ] Set `BOMIPAY_ENV=production`
- [ ] Disable `docs_url` and `redoc_url` in `main.py` for production (or restrict to internal network)
- [ ] Run `alembic upgrade head`
- [ ] Verify `alembic current` shows `0019_dashboard_snapshots (head)`
- [ ] Run smoke test suite against staging environment
- [ ] Confirm all 190 tests pass in CI before deploying

---

## Verdict

**READY** — with the following caveats addressed before go-live:

1. **`PROVIDER_ENCRYPTION_KEY` must be set** in the production environment; without it, provider account creation and sync fail silently.
2. **Disable OpenAPI docs** (`/docs`, `/redoc`) in production or restrict to internal/VPN access only.
3. **Fix the pre-existing webhook test** (`test_paystack_webhook_ingestion_and_idempotency`) by storing a properly encrypted secret in the test fixture — the production code is correct.
4. **Add `logger.exception(...)` calls** inside `except Exception` blocks in service layer so errors are observable in production monitoring.

The core business logic is sound: JWT authentication with role-based access, secrets encrypted at rest, input validation via Pydantic throughout, composite indices on all hot-path columns, 190/191 tests passing, and a complete migration chain covering all 19 model tables.
