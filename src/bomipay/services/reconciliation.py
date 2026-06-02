import csv
import hashlib
import io
import logging
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.reconciliation import (
    ExpectedPayment,
    ExpectedPaymentImportBatch,
    ExpectedPaymentStatus,
    ReconciliationMatchStatus,
    ReconciliationResult,
    ReconciliationRun,
    ReconciliationRunStatus,
)
from ..models.transaction import Transaction
from ..schemas.reconciliation import ExpectedPaymentImportItem

logger = logging.getLogger("bomipay.reconciliation")

MATCHING_POLICY_VERSION = "1.0"
WEAK_MATCH_WINDOW_DAYS = 2


class ReconciliationService:
    @staticmethod
    async def parse_expected_payment_csv(file) -> tuple[list[ExpectedPaymentImportItem], list[str]]:
        content = await file.read()
        decoded = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded))
        items: list[ExpectedPaymentImportItem] = []
        errors: list[str] = []

        for row_index, row in enumerate(reader, start=1):
            payload = {
                "reference": row.get("reference") or row.get("Reference") or row.get("external_reference"),
                "amount": int(row.get("amount", 0)) if row.get("amount") else None,
                "currency": row.get("currency") or row.get("Currency"),
                "due_date": row.get("due_date") or row.get("dueDate") or row.get("settled_at"),
                "customer_name": row.get("customer_name") or row.get("CustomerName"),
                "customer_email": row.get("customer_email") or row.get("CustomerEmail"),
                "customer_phone": row.get("customer_phone") or row.get("CustomerPhone"),
                "metadata_json": None,
            }
            try:
                items.append(ExpectedPaymentImportItem.model_validate(payload))
            except ValidationError as exc:
                errors.append(f"row {row_index}: {exc}")
        return items, errors

    @staticmethod
    def validate_expected_payments(items: list[dict[str, Any]]) -> tuple[list[ExpectedPaymentImportItem], list[str]]:
        validated_items: list[ExpectedPaymentImportItem] = []
        errors: list[str] = []

        for row_index, row in enumerate(items, start=1):
            try:
                validated_items.append(ExpectedPaymentImportItem.model_validate(row))
            except ValidationError as exc:
                errors.append(f"row {row_index}: {exc}")
        return validated_items, errors

    @staticmethod
    async def create_import_batch(
        db: AsyncSession,
        merchant_id: str,
        rows_received: int,
        file_name: Optional[str] = None,
        file_hash: Optional[str] = None,
    ) -> ExpectedPaymentImportBatch:
        batch = ExpectedPaymentImportBatch(
            merchant_id=merchant_id,
            file_name=file_name,
            file_hash=file_hash,
            rows_received=rows_received,
            rows_inserted=0,
            rows_skipped=0,
            rows_rejected=0,
        )
        db.add(batch)
        await db.flush()
        return batch

    @staticmethod
    def compute_file_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    async def import_expected_payments(
        db: AsyncSession,
        merchant_id: str,
        items: Iterable[ExpectedPaymentImportItem],
        rows_received: Optional[int] = None,
        file_name: Optional[str] = None,
        file_hash: Optional[str] = None,
    ) -> dict[str, Any]:
        rows_inserted = 0
        rows_skipped = 0
        rows_rejected = 0
        errors: list[str] = []

        items = list(items)
        if rows_received is None:
            rows_received = len(items)
        rows_rejected = max(0, rows_received - len(items))

        batch = await ReconciliationService.create_import_batch(
            db, merchant_id, rows_received, file_name=file_name, file_hash=file_hash
        )

        for item_index, item in enumerate(items, start=1):
            try:
                existing = await db.execute(
                    select(ExpectedPayment).where(
                        ExpectedPayment.merchant_id == merchant_id,
                        ExpectedPayment.reference == item.reference,
                        ExpectedPayment.amount == item.amount,
                        ExpectedPayment.currency == item.currency,
                        ExpectedPayment.due_date == item.due_date,
                    )
                )
                if existing.scalars().first():
                    rows_skipped += 1
                    continue

                expected_payment = ExpectedPayment(
                    merchant_id=merchant_id,
                    import_batch_id=batch.id,
                    reference=item.reference,
                    amount=item.amount,
                    currency=item.currency,
                    due_date=item.due_date,
                    customer_name=item.customer_name,
                    customer_email=item.customer_email,
                    customer_phone=item.customer_phone,
                    status=ExpectedPaymentStatus.pending,
                    metadata_json=item.metadata_json,
                )
                db.add(expected_payment)
                rows_inserted += 1
            except Exception as exc:
                rows_rejected += 1
                errors.append(f"row {item_index}: {exc}")

        batch.rows_inserted = rows_inserted
        batch.rows_skipped = rows_skipped
        batch.rows_rejected = rows_rejected
        await db.flush()

        logger.info(
            "reconciliation.import.complete",
            extra={
                "merchant_id": merchant_id,
                "batch_id": str(batch.id),
                "rows_received": rows_received,
                "rows_inserted": rows_inserted,
                "rows_skipped": rows_skipped,
                "rows_rejected": rows_rejected,
            },
        )

        return {
            "rows_received": rows_received,
            "rows_inserted": rows_inserted,
            "rows_skipped": rows_skipped,
            "rows_rejected": rows_rejected,
            "errors": errors,
        }

    @staticmethod
    async def get_expected_payments_for_range(
        db: AsyncSession,
        merchant_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[ExpectedPayment]:
        result = await db.execute(
            select(ExpectedPayment)
            .where(ExpectedPayment.merchant_id == merchant_id)
            .where(ExpectedPayment.due_date >= date_from)
            .where(ExpectedPayment.due_date <= date_to)
            .order_by(ExpectedPayment.due_date.asc(), ExpectedPayment.id.asc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_transactions_for_range(
        db: AsyncSession,
        merchant_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> list[Transaction]:
        result = await db.execute(
            select(Transaction)
            .where(Transaction.merchant_id == merchant_id)
            .where(Transaction.created_at >= date_from)
            .where(Transaction.created_at <= date_to)
            .order_by(Transaction.created_at.asc(), Transaction.id.asc())
        )
        return result.scalars().all()

    @staticmethod
    def _normalize_string(value: Optional[str]) -> str:
        if not value:
            return ""
        return value.strip().lower()

    @staticmethod
    def _same_reference(expected: ExpectedPayment, transaction: Transaction) -> bool:
        normalized_reference = ReconciliationService._normalize_string(expected.reference)
        return normalized_reference in {
            ReconciliationService._normalize_string(transaction.internal_reference),
            ReconciliationService._normalize_string(transaction.external_reference),
            ReconciliationService._normalize_string(transaction.provider_transaction_id),
        }

    @staticmethod
    def _same_amount_currency(expected: ExpectedPayment, transaction: Transaction) -> bool:
        return transaction.amount == expected.amount and transaction.currency == expected.currency

    @staticmethod
    def _same_customer(expected: ExpectedPayment, transaction: Transaction) -> bool:
        if expected.customer_email and transaction.customer_email:
            return ReconciliationService._normalize_string(expected.customer_email) == ReconciliationService._normalize_string(transaction.customer_email)
        if expected.customer_phone and transaction.customer_phone:
            return ReconciliationService._normalize_string(expected.customer_phone) == ReconciliationService._normalize_string(transaction.customer_phone)
        if expected.customer_name and transaction.customer_name:
            return ReconciliationService._normalize_string(expected.customer_name) == ReconciliationService._normalize_string(transaction.customer_name)
        return False

    @staticmethod
    def _transaction_within_window(expected: ExpectedPayment, transaction: Transaction) -> bool:
        if transaction.created_at is None:
            return False
        window = timedelta(days=WEAK_MATCH_WINDOW_DAYS)
        return expected.due_date - window <= transaction.created_at <= expected.due_date + window

    @staticmethod
    def _select_candidate(candidates: list[Transaction]) -> Optional[Transaction]:
        if not candidates:
            return None
        return sorted(candidates, key=lambda t: (t.created_at or datetime.min, str(t.id)))[0]

    @staticmethod
    def score_match(expected: ExpectedPayment, transaction: Transaction) -> tuple[float, ReconciliationMatchStatus, str]:
        reference_matches = ReconciliationService._same_reference(expected, transaction)
        amount_currency_matches = ReconciliationService._same_amount_currency(expected, transaction)
        customer_matches = ReconciliationService._same_customer(expected, transaction)

        if reference_matches and amount_currency_matches:
            return 1.0, ReconciliationMatchStatus.matched, "Exact reference, amount, and currency match"
        if reference_matches and transaction.currency == expected.currency:
            if transaction.amount < expected.amount:
                return 0.7, ReconciliationMatchStatus.underpaid, "Reference matches but amount is lower than expected"
            if transaction.amount > expected.amount:
                return 0.7, ReconciliationMatchStatus.overpaid, "Reference matches but amount is higher than expected"
            return 0.6, ReconciliationMatchStatus.weak, "Reference matches but currency differs"
        if amount_currency_matches and customer_matches:
            return 0.65, ReconciliationMatchStatus.matched, "Amount and customer match"
        if amount_currency_matches and ReconciliationService._transaction_within_window(expected, transaction):
            return 0.4, ReconciliationMatchStatus.weak, "Amount and currency match within expected date window"
        return 0.0, ReconciliationMatchStatus.unmatched, "No deterministic match candidate"

    @staticmethod
    async def create_reconciliation_run(
        db: AsyncSession,
        merchant_id: str,
        date_from: datetime,
        date_to: datetime,
        run_name: str | None = None,
    ) -> ReconciliationRun:
        run = ReconciliationRun(
            merchant_id=merchant_id,
            date_from=date_from,
            date_to=date_to,
            matching_policy_version=MATCHING_POLICY_VERSION,
            source_expected_payment_count=0,
            status=ReconciliationRunStatus.running,
            run_name=run_name,
        )
        db.add(run)
        await db.flush()
        logger.info(
            "reconciliation.run.start",
            extra={"merchant_id": merchant_id, "run_id": str(run.id), "date_from": date_from, "date_to": date_to},
        )
        return run

    @staticmethod
    async def execute_reconciliation_run(db: AsyncSession, run: ReconciliationRun) -> ReconciliationRun:
        expected_payments = await ReconciliationService.get_expected_payments_for_range(
            db, run.merchant_id, run.date_from, run.date_to
        )
        transactions = await ReconciliationService.get_transactions_for_range(
            db, run.merchant_id, run.date_from, run.date_to
        )

        def expected_sort_key(expected: ExpectedPayment) -> tuple[int, int, str, datetime, str]:
            exact_reference = 0 if any(ReconciliationService._same_reference(expected, t) for t in transactions) else 1
            strong_customer = 0 if any(
                ReconciliationService._same_amount_currency(expected, t) and ReconciliationService._same_customer(expected, t)
                for t in transactions
            ) else 1
            return (
                exact_reference,
                strong_customer,
                ReconciliationService._normalize_string(expected.reference),
                expected.due_date,
                str(expected.id),
            )

        expected_payments.sort(key=expected_sort_key)

        run.source_expected_payment_count = len(expected_payments)
        await db.flush()

        transaction_candidates = list(transactions)
        duplicate_tracker: set[str] = set()

        for expected in expected_payments:
            exact_candidates = [
                t for t in transaction_candidates
                if ReconciliationService._same_reference(expected, t) and ReconciliationService._same_amount_currency(expected, t)
            ]
            if len(exact_candidates) > 1:
                selected_status = ReconciliationMatchStatus.ambiguous
                selected_score = 0.2
                selected_notes = "Multiple exact reference and amount matches found"
                selected_transaction = None
            elif exact_candidates:
                selected_transaction = ReconciliationService._select_candidate(exact_candidates)
                selected_score, selected_status, selected_notes = ReconciliationService.score_match(expected, selected_transaction)
            else:
                strong_reference_candidates = [
                    t for t in transaction_candidates
                    if ReconciliationService._same_reference(expected, t) and t.currency == expected.currency
                ]
                if len(strong_reference_candidates) > 1:
                    selected_status = ReconciliationMatchStatus.ambiguous
                    selected_score = 0.2
                    selected_notes = "Multiple strong reference-only matches found"
                    selected_transaction = None
                elif strong_reference_candidates:
                    selected_transaction = ReconciliationService._select_candidate(strong_reference_candidates)
                    selected_score, selected_status, selected_notes = ReconciliationService.score_match(expected, selected_transaction)
                else:
                    customer_candidates = [
                        t for t in transaction_candidates
                        if ReconciliationService._same_amount_currency(expected, t) and ReconciliationService._same_customer(expected, t)
                    ]
                    if len(customer_candidates) > 1:
                        selected_status = ReconciliationMatchStatus.ambiguous
                        selected_score = 0.2
                        selected_notes = "Multiple strong customer matches found"
                        selected_transaction = None
                    elif customer_candidates:
                        selected_transaction = ReconciliationService._select_candidate(customer_candidates)
                        selected_score, selected_status, selected_notes = ReconciliationService.score_match(expected, selected_transaction)
                    else:
                        weak_candidates = [
                            t for t in transaction_candidates
                            if ReconciliationService._same_amount_currency(expected, t)
                            and ReconciliationService._transaction_within_window(expected, t)
                        ]
                        if len(weak_candidates) > 1:
                            selected_status = ReconciliationMatchStatus.ambiguous
                            selected_score = 0.2
                            selected_notes = "Multiple weak window matches found"
                            selected_transaction = None
                        elif weak_candidates:
                            selected_transaction = ReconciliationService._select_candidate(weak_candidates)
                            selected_score, selected_status, selected_notes = ReconciliationService.score_match(expected, selected_transaction)
                        else:
                            selected_status = ReconciliationMatchStatus.unmatched
                            selected_score = 0.0
                            selected_notes = "No acceptable match candidate found"
                            selected_transaction = None

            if selected_transaction and str(selected_transaction.id) in duplicate_tracker:
                selected_status = ReconciliationMatchStatus.duplicate
                selected_score = min(selected_score, 0.3)
                selected_notes = "Expected payment matches a transaction already matched in this run"
            elif selected_transaction and selected_status not in {ReconciliationMatchStatus.ambiguous, ReconciliationMatchStatus.unmatched}:
                duplicate_tracker.add(str(selected_transaction.id))

            if selected_status == ReconciliationMatchStatus.matched:
                expected.status = ExpectedPaymentStatus.matched
                await db.flush()

            result = ReconciliationResult(
                run_id=run.id,
                expected_payment_id=expected.id,
                transaction_id=selected_transaction.id if selected_transaction else None,
                match_status=selected_status,
                confidence_score=selected_score,
                notes=selected_notes,
            )
            db.add(result)

            logger.info(
                "reconciliation.match.result",
                extra={
                    "merchant_id": run.merchant_id,
                    "run_id": str(run.id),
                    "expected_payment_id": str(expected.id),
                    "transaction_id": str(selected_transaction.id) if selected_transaction else None,
                    "match_status": selected_status.value,
                    "confidence_score": selected_score,
                },
            )

        run.status = ReconciliationRunStatus.completed
        await db.flush()
        await db.refresh(run)

        logger.info(
            "reconciliation.run.complete",
            extra={
                "merchant_id": run.merchant_id,
                "run_id": str(run.id),
                "source_expected_payment_count": run.source_expected_payment_count,
            },
        )
        return run

    @staticmethod
    async def get_run_summary(db: AsyncSession, run_id: str) -> dict[str, Any]:
        result = await db.execute(select(ReconciliationRun).where(ReconciliationRun.id == run_id))
        run = result.scalars().first()
        if not run:
            raise ValueError("Reconciliation run not found")

        result_rows = await db.execute(
            select(ReconciliationResult, ExpectedPayment)
            .where(ReconciliationResult.run_id == run_id)
            .join(ExpectedPayment, ReconciliationResult.expected_payment_id == ExpectedPayment.id)
        )
        rows = result_rows.all()
        expected_amount = sum(row[1].amount for row in rows)
        matched_amount = sum(row[1].amount for row in rows if row[0].match_status == ReconciliationMatchStatus.matched)

        return {
            "run_id": run.id,
            "merchant_id": run.merchant_id,
            "run_name": run.run_name,
            "matching_policy_version": run.matching_policy_version,
            "date_from": run.date_from,
            "date_to": run.date_to,
            "status": run.status.value,
            "expected_count": len(rows),
            "matched_count": sum(1 for row in rows if row[0].match_status == ReconciliationMatchStatus.matched),
            "partial_count": sum(1 for row in rows if row[0].match_status == ReconciliationMatchStatus.weak),
            "unmatched_count": sum(1 for row in rows if row[0].match_status == ReconciliationMatchStatus.unmatched),
            "duplicate_count": sum(1 for row in rows if row[0].match_status == ReconciliationMatchStatus.duplicate),
            "underpaid_count": sum(1 for row in rows if row[0].match_status == ReconciliationMatchStatus.underpaid),
            "overpaid_count": sum(1 for row in rows if row[0].match_status == ReconciliationMatchStatus.overpaid),
            "ambiguous_count": sum(1 for row in rows if row[0].match_status == ReconciliationMatchStatus.ambiguous),
            "total_expected_amount": expected_amount,
            "total_matched_amount": matched_amount,
        }

    @staticmethod
    async def get_reconciliation_run(db: AsyncSession, run_id: str, merchant_id: str | None = None) -> ReconciliationRun | None:
        query = select(ReconciliationRun).where(ReconciliationRun.id == run_id)
        if merchant_id:
            query = query.where(ReconciliationRun.merchant_id == merchant_id)
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def list_reconciliation_runs(db: AsyncSession, merchant_id: str | None = None) -> list[ReconciliationRun]:
        query = select(ReconciliationRun)
        if merchant_id:
            query = query.where(ReconciliationRun.merchant_id == merchant_id)
        result = await db.execute(query.order_by(ReconciliationRun.created_at.desc()))
        return result.scalars().all()

    @staticmethod
    async def list_expected_payments(
        db: AsyncSession,
        merchant_id: str,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[ExpectedPayment]:
        query = select(ExpectedPayment).where(ExpectedPayment.merchant_id == merchant_id)
        if status:
            query = query.where(ExpectedPayment.status == status)
        if date_from:
            query = query.where(ExpectedPayment.due_date >= date_from)
        if date_to:
            query = query.where(ExpectedPayment.due_date <= date_to)
        result = await db.execute(query.order_by(ExpectedPayment.due_date.desc()))
        return result.scalars().all()

    @staticmethod
    async def get_reconciliation_results(db: AsyncSession, run_id: str) -> list[ReconciliationResult]:
        result = await db.execute(
            select(ReconciliationResult)
            .where(ReconciliationResult.run_id == run_id)
            .order_by(ReconciliationResult.created_at.asc())
        )
        return result.scalars().all()
