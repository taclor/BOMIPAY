---
description: Describe when these instructions should be loaded by the agent based on task context
# applyTo: 'Describe when these instructions should be loaded by the agent based on task context' # when provided, instructions will automatically be added to the request context when the pattern matches an attached file
---

<!-- Tip: Use /create-instructions in chat to generate content with agent assistance -->

You are now the responsible AI backend developer for Bomi Pay.

The current codebase already contains the first backend foundation: FastAPI structure, authentication, JWT, merchants, provider accounts, Paystack webhook ingestion, transactions, transaction events, alerts, notifications, reconciliation, audit logs, Alembic migrations, and tests.

But this is not enough.

Bomi Pay must become a production-ready AI payment intelligence layer. Do not treat this like a demo. Do not only write explanations. You must create tasks, save them inside the repo, execute them one by one, write code, write migrations, write tests, and keep working until the backend is complete.

==================================================
MISSION
=======

Transform the current Bomi Pay backend from a basic payment monitoring MVP into a production-grade payment intelligence operating system.

The final system must support:

1. Merchant onboarding
2. Provider connection
3. Bank account management
4. Data source management
5. Webhook ingestion
6. Provider API polling/sync jobs
7. Canonical transaction model
8. Bank statement upload and parsing
9. Reconciliation
10. Incidents
11. Alerts
12. Disputes
13. Money-at-risk analytics
14. Mission Control dashboard
15. Unified payment timeline
16. Action Center
17. Payment graph / ontology API
18. AI assistant grounded in internal records
19. Audit logs
20. Tests for all critical flows

==================================================
FIRST ACTION — CREATE INTERNAL TASK LIST
========================================

Before writing feature code, create this file:

docs/internal/BOMI_BACKEND_COMPLETION_TASKS.md

This file must contain a checklist of all tasks below.

Use this format:

* [ ] TASK-001: Fix critical backend foundation issues
* [ ] TASK-002: Add Bank Account Management
* [ ] TASK-003: Add Data Source Management
* [ ] TASK-004: Add Bank Statement Import
* [ ] TASK-005: Add Provider Sync Jobs
* [ ] TASK-006: Add Incident Center
* [ ] TASK-007: Add Money-at-Risk Analytics
* [ ] TASK-008: Add Mission Control Dashboard API
* [ ] TASK-009: Add Unified Payment Timeline API
* [ ] TASK-010: Add Action Center API
* [ ] TASK-011: Add Payment Graph / Ontology API
* [ ] TASK-012: Extend AI Assistant
* [ ] TASK-013: Add complete tests
* [ ] TASK-014: Run migrations and test suite
* [ ] TASK-015: Final production-readiness review

After each completed task, update the checkbox to [x] and add a short implementation note.

==================================================
TASK-001 — FIX CRITICAL BACKEND FOUNDATION
==========================================

Fix these before adding new features:

1. Fix FastAPI lifespan:
   Change incorrect non-async lifespan to async lifespan.

2. Fix CORS:
   Remove wildcard origins with credentials.
   Use environment-based allowed origins.

3. Fix refresh token UUID handling:
   Convert user_id from token into UUID before lookup.

4. Strengthen webhook idempotency:
   Add DB unique constraint on:
   provider_name + provider_event_id

5. Stop trusting merchant_id from provider metadata:
   Resolve merchant from provider account, webhook secret, or registered provider connection.

6. Replace Float confidence score:
   Use integer confidence_score_bps between 0 and 10000.

7. Improve provider adapter contract:
   Ensure all providers implement:

* verify_transaction
* fetch_transaction
* fetch_transactions
* fetch_settlements
* fetch_transfers
* fetch_refunds
* get_provider_health
* process_webhook

Add tests for all fixes.

==================================================
TASK-002 — BANK ACCOUNT MANAGEMENT
==================================

Add merchant bank account management.

Create model:
bank_accounts

Fields:

* id UUID
* merchant_id UUID
* bank_name
* bank_code nullable
* account_number_encrypted
* account_number_last4
* account_name
* currency default NGN
* purpose enum: settlement, operations, payout, reconciliation
* verification_status enum: unverified, pending, verified, failed
* status enum: active, inactive, archived
* metadata_json
* created_at
* updated_at

APIs:

* POST /v1/bank-accounts
* GET /v1/bank-accounts?merchant_id=
* GET /v1/bank-accounts/{bank_account_id}
* PATCH /v1/bank-accounts/{bank_account_id}
* DELETE /v1/bank-accounts/{bank_account_id}
* POST /v1/bank-accounts/{bank_account_id}/verify

Rules:

* Enforce RBAC.
* Enforce tenant isolation.
* Mask account numbers in responses.
* Never log full account numbers.
* Audit create, update, delete, verify.
* Verification may be stubbed behind a clean adapter interface.

==================================================
TASK-003 — DATA SOURCE MANAGEMENT
=================================

Add data source management so merchants know where Bomi Pay gets data from.

Create model:
data_sources

Fields:

* id UUID
* merchant_id UUID
* source_type enum: provider_api, provider_webhook, bank_statement_upload, csv_upload, erp_export, pos_export, manual_entry
* provider_name nullable
* provider_account_id nullable
* display_name
* status enum: active, inactive, error, pending_setup
* last_sync_at nullable
* last_success_at nullable
* last_error_at nullable
* last_error_message nullable
* configuration_json
* created_at
* updated_at

APIs:

* POST /v1/data-sources
* GET /v1/data-sources?merchant_id=
* GET /v1/data-sources/{data_source_id}
* PATCH /v1/data-sources/{data_source_id}
* POST /v1/data-sources/{data_source_id}/test
* GET /v1/data-sources/{data_source_id}/sync-status

Rules:

* Provider accounts must create or link to provider data sources.
* Webhooks must update provider webhook source health.
* Test endpoint must not mutate financial records.
* Audit all changes.

==================================================
TASK-004 — BANK STATEMENT IMPORT
================================

Add bank statement upload and parsing.

Create models:

bank_statement_imports:

* id UUID
* merchant_id UUID
* bank_account_id nullable
* file_name
* file_type enum: csv, xlsx
* status enum: uploaded, processing, completed, failed
* total_rows
* processed_rows
* failed_rows
* error_summary
* created_at
* completed_at nullable

bank_statement_entries:

* id UUID
* merchant_id UUID
* import_id UUID
* bank_account_id nullable
* entry_date
* value_date nullable
* description
* reference nullable
* debit_amount_minor integer default 0
* credit_amount_minor integer default 0
* currency
* balance_after_minor nullable
* counterparty_name nullable
* raw_row_json
* normalized_hash
* created_at

APIs:

* POST /v1/bank-statements/import
* GET /v1/bank-statements/imports?merchant_id=
* GET /v1/bank-statements/imports/{import_id}
* GET /v1/bank-statements/imports/{import_id}/entries
* GET /v1/bank-statements/entries?merchant_id=&date_from=&date_to=

Rules:

* Use minor units only.
* No floats.
* Store raw row and normalized row.
* Use normalized_hash for duplicate protection.
* Failed rows must be traceable.
* CSV first, XLSX-ready interface.
* Tests for duplicate upload, invalid rows, and tenant isolation.

==================================================
TASK-005 — PROVIDER SYNC JOBS
=============================

Add provider polling because webhooks alone are not enough.

Create model:
provider_sync_jobs

Fields:

* id UUID
* merchant_id UUID
* provider_account_id UUID
* sync_type enum: transactions, settlements, transfers, refunds, provider_health
* status enum: queued, running, completed, failed, cancelled
* date_from nullable
* date_to nullable
* started_at nullable
* completed_at nullable
* records_seen integer
* records_created integer
* records_updated integer
* error_message nullable
* correlation_id
* created_at

APIs:

* POST /v1/providers/{provider_account_id}/sync/transactions
* POST /v1/providers/{provider_account_id}/sync/settlements
* POST /v1/providers/{provider_account_id}/sync/transfers
* POST /v1/providers/{provider_account_id}/sync/refunds
* GET /v1/providers/{provider_account_id}/sync-jobs
* GET /v1/provider-sync-jobs/{job_id}

Rules:

* Sync jobs must be idempotent.
* Use provider adapter interface.
* Store raw provider response.
* Normalize into canonical events.
* Webhook and polling must converge into same transaction model.
* Tests for duplicate sync, provider timeout, partial failure, retry safety.

==================================================
TASK-006 — INCIDENT CENTER
==========================

Add operational incident management.

Create models:

incidents:

* id UUID
* merchant_id UUID
* title
* incident_type enum: provider_failure_spike, settlement_delay, webhook_failure, reconciliation_mismatch, duplicate_payment_risk, hanging_transaction, bank_statement_mismatch
* severity enum: low, medium, high, critical
* status enum: open, acknowledged, investigating, resolved, closed
* provider_name nullable
* affected_amount_minor
* affected_transaction_count
* started_at
* ended_at nullable
* summary
* ai_summary nullable
* created_at
* updated_at

incident_events:

* id UUID
* incident_id UUID
* event_type
* actor_user_id nullable
* message
* metadata_json
* created_at

APIs:

* GET /v1/incidents?merchant_id=&status=&severity=
* GET /v1/incidents/{incident_id}
* POST /v1/incidents/{incident_id}/acknowledge
* POST /v1/incidents/{incident_id}/resolve
* POST /v1/incidents/{incident_id}/events

Rules:

* Alerts can create incidents.
* Related alerts may be grouped.
* Incident timeline is append-only.
* AI can summarize but cannot resolve.
* Audit status changes.
* Tests for creation, grouping, acknowledgement, resolution, RBAC.

==================================================
TASK-007 — MONEY-AT-RISK ANALYTICS
==================================

Add money-at-risk calculation.

API:

* GET /v1/analytics/money-at-risk?merchant_id=&date_from=&date_to=

Return:

* total_money_at_risk_minor
* failed_payments_amount_minor
* hanging_payments_amount_minor
* unsettled_successful_payments_amount_minor
* settlement_mismatch_amount_minor
* duplicate_payment_risk_amount_minor
* unresolved_dispute_amount_minor
* affected_transaction_count
* top_providers_by_risk
* top_incidents
* recommended_actions

Rules:

* Numbers must come from deterministic database queries.
* AI may suggest actions, but cannot invent numbers.
* No floats.
* Add correctness tests.

==================================================
TASK-008 — MISSION CONTROL DASHBOARD
====================================

Add main dashboard API.

API:

* GET /v1/dashboard/mission-control?merchant_id=

Return:

* payment_success_rate_bps
* failed_transaction_count
* money_at_risk_minor
* pending_settlements_minor
* open_incident_count
* provider_health_summary
* reconciliation_status
* ai_insight_summary
* top_actions

Rules:

* Fast query.
* Tenant safe.
* No controller business logic.
* Tests for calculations.

==================================================
TASK-009 — UNIFIED PAYMENT TIMELINE
===================================

Add unified timeline.

API:

* GET /v1/timeline/payments?merchant_id=&date_from=&date_to=&status=&provider=&page=&page_size=

Return mixed normalized events:

* transaction_created
* webhook_received
* provider_status_changed
* settlement_received
* bank_statement_entry_imported
* reconciliation_match_created
* dispute_opened
* incident_created
* alert_created

Rules:

* Paginated.
* Ordered by event time descending.
* Tenant safe.
* Tests required.

==================================================
TASK-010 — ACTION CENTER
========================

Add action center.

API:

* GET /v1/action-center?merchant_id=

Return prioritized actions:

* investigate_failed_payment
* upload_bank_statement
* resolve_unmatched_settlement
* acknowledge_incident
* open_dispute
* retry_provider_sync
* review_duplicate_payment_risk

Fields:

* action_id
* action_type
* priority
* title
* description
* related_entity_type
* related_entity_id
* recommended_next_step
* created_at

Rules:

* Deterministic priority rules first.
* AI can improve wording only.
* Tests required.

==================================================
TASK-011 — PAYMENT GRAPH / ONTOLOGY API
=======================================

Add read-only payment graph API.

Graph must connect:
Customer -> Payment Request -> Transaction -> Transaction Events -> Settlement -> Bank Statement Entry -> Reconciliation Result -> Dispute -> Incident -> Alert

APIs:

* GET /v1/payment-graph/transactions/{transaction_id}
* GET /v1/payment-graph/incidents/{incident_id}
* GET /v1/payment-graph/merchants/{merchant_id}/overview

Response:
{
"nodes": [],
"edges": []
}

Rules:

* Use PostgreSQL relational queries for now.
* No graph database yet.
* Read-only.
* Tenant safe.
* AI assistant must be able to use this graph.
* Tests required.

==================================================
TASK-012 — AI ASSISTANT EXTENSION
=================================

Extend AI assistant to use real internal records.

AI context must include:

* transaction timeline
* payment graph
* incidents
* money-at-risk analytics
* bank statement entries
* provider sync history
* data source health
* reconciliation results
* disputes
* alerts

Support questions:

* Why is my money at risk?
* Which provider is causing most problems?
* Which bank account has settlement mismatch?
* What should I do first today?
* Show unresolved money issues.
* Why is this settlement not matching my bank statement?
* Why did this transaction fail?

Rules:

* AI must not mutate records.
* AI must not invent facts.
* AI must return:

  * answer
  * confidence
  * cited_internal_records
  * suggested_actions
  * limitations
* Tests must ensure AI uses retrieved records only.

==================================================
TASK-013 — COMPLETE TESTS
=========================

Add or update tests for:

* auth
* RBAC
* tenant isolation
* bank accounts
* data sources
* bank statement import
* provider sync jobs
* webhook idempotency
* canonical transaction normalization
* alerts
* incidents
* money-at-risk
* dashboard
* timeline
* action center
* payment graph
* reconciliation
* disputes
* AI assistant grounding
* audit logging

No feature is complete without tests.

==================================================
TASK-014 — RUN MIGRATIONS AND TEST SUITE
========================================

Run:

* alembic upgrade head
* pytest

Fix all failures.

The repo must be left in a running state.

==================================================
TASK-015 — FINAL PRODUCTION READINESS REVIEW
============================================

Create:

docs/internal/BOMI_BACKEND_COMPLETION_REPORT.md

Include:

* completed tasks
* migrations added
* APIs added
* tests added
* known limitations
* remaining risks
* next recommended step

==================================================
DELIVERY RULES
==============

Do not stop after creating files.
Do not only explain.
Do not produce placeholder code where real implementation is needed.
Do not skip migrations.
Do not skip tests.
Do not put business logic inside controllers.
Do not use floats for money.
Do not log secrets or full account numbers.
Do not let AI mutate financial records.
Do not break existing tests.
Do not leave the repo half-working.

Work task by task until completion.

At the end, the backend must be closer to production-ready and must fully represent the Bomi Pay intelligence layer.
