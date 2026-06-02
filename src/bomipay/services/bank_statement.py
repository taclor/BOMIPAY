import csv
import hashlib
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.bank_statement import BankStatementEntry, BankStatementImport, BankStatementImportStatus

logger = logging.getLogger("bomipay")


def _normalize_hash(merchant_id: str, row: dict) -> str:
    payload = json.dumps(
        {
            "merchant_id": merchant_id,
            "entry_date": str(row.get("entry_date", "")),
            "description": str(row.get("description", "")),
            "debit_amount_minor": row.get("debit_amount_minor", 0),
            "credit_amount_minor": row.get("credit_amount_minor", 0),
            "reference": str(row.get("reference", "")),
            "currency": str(row.get("currency", "NGN")),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_csv_rows(file_content: bytes) -> list[dict]:
    reader = csv.DictReader(io.StringIO(file_content.decode("utf-8", errors="replace")))
    rows = []
    for row in reader:
        rows.append(dict(row))
    return rows


def normalize_row(raw: dict, currency: str = "NGN") -> Optional[dict]:
    try:
        description = (raw.get("description") or raw.get("narration") or raw.get("details") or "").strip()
        if not description:
            return None

        def parse_amount(key_list) -> int:
            for k in key_list:
                val = raw.get(k, "").replace(",", "").strip()
                if val:
                    try:
                        return int(float(val) * 100)
                    except (ValueError, TypeError):
                        pass
            return 0

        debit = parse_amount(["debit", "debit_amount", "withdrawal"])
        credit = parse_amount(["credit", "credit_amount", "deposit"])

        entry_date_raw = raw.get("date") or raw.get("entry_date") or raw.get("transaction_date") or ""
        try:
            entry_date = datetime.fromisoformat(entry_date_raw.strip())
        except (ValueError, AttributeError):
            return None

        reference = (raw.get("reference") or raw.get("ref") or raw.get("transaction_id") or "").strip() or None
        currency_val = (raw.get("currency") or currency).strip()

        balance_raw = raw.get("balance") or raw.get("balance_after") or ""
        balance_after = None
        if balance_raw:
            try:
                balance_after = int(float(str(balance_raw).replace(",", "").strip()) * 100)
            except (ValueError, TypeError):
                pass

        return {
            "entry_date": entry_date,
            "value_date": None,
            "description": description,
            "reference": reference,
            "debit_amount_minor": debit,
            "credit_amount_minor": credit,
            "currency": currency_val,
            "balance_after_minor": balance_after,
            "counterparty_name": (raw.get("counterparty") or raw.get("payee") or "").strip() or None,
        }
    except Exception:
        return None


class BankStatementService:
    @staticmethod
    async def create_import(
        db: AsyncSession,
        merchant_id: str,
        file_name: str,
        file_type: str,
        bank_account_id: Optional[str] = None,
    ) -> BankStatementImport:
        imp = BankStatementImport(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            bank_account_id=bank_account_id,
            file_name=file_name,
            file_type=file_type,
            status=BankStatementImportStatus.uploaded.value,
        )
        db.add(imp)
        await db.flush()
        return imp

    @staticmethod
    async def process_csv_import(
        db: AsyncSession,
        import_record: BankStatementImport,
        file_content: bytes,
        default_currency: str = "NGN",
    ) -> BankStatementImport:
        import_record.status = BankStatementImportStatus.processing.value
        await db.flush()

        raw_rows = parse_csv_rows(file_content)
        import_record.total_rows = len(raw_rows)

        processed = 0
        failed = 0
        errors: list[dict] = []

        for idx, raw in enumerate(raw_rows):
            normalized = normalize_row(raw, default_currency)
            if normalized is None:
                failed += 1
                errors.append({"row": idx + 1, "error": "Failed to normalize row", "raw": raw})
                continue

            normalized_hash = _normalize_hash(str(import_record.merchant_id), normalized)

            # Idempotency check: skip if hash already exists
            existing = await db.execute(
                select(BankStatementEntry).where(BankStatementEntry.normalized_hash == normalized_hash)
            )
            if existing.scalar_one_or_none() is not None:
                processed += 1
                continue

            entry = BankStatementEntry(
                id=uuid.uuid4(),
                merchant_id=import_record.merchant_id,
                import_id=import_record.id,
                bank_account_id=import_record.bank_account_id,
                entry_date=normalized["entry_date"],
                value_date=normalized["value_date"],
                description=normalized["description"],
                reference=normalized["reference"],
                debit_amount_minor=normalized["debit_amount_minor"],
                credit_amount_minor=normalized["credit_amount_minor"],
                currency=normalized["currency"],
                balance_after_minor=normalized["balance_after_minor"],
                counterparty_name=normalized["counterparty_name"],
                raw_row_json=raw,
                normalized_hash=normalized_hash,
                created_at=datetime.now(timezone.utc),
            )
            db.add(entry)
            processed += 1

        import_record.processed_rows = processed
        import_record.failed_rows = failed
        import_record.error_summary = errors or None
        import_record.status = (
            BankStatementImportStatus.completed.value
            if failed == 0
            else (BankStatementImportStatus.failed.value if processed == 0 else BankStatementImportStatus.completed.value)
        )
        import_record.completed_at = datetime.now(timezone.utc)
        await db.flush()
        logger.info(
            "bank_statement.processed",
            extra={
                "import_id": str(import_record.id),
                "total": import_record.total_rows,
                "processed": processed,
                "failed": failed,
            },
        )
        return import_record

    @staticmethod
    async def get_import(db: AsyncSession, import_id: str) -> Optional[BankStatementImport]:
        result = await db.execute(select(BankStatementImport).where(BankStatementImport.id == import_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_imports(db: AsyncSession, merchant_id: str) -> list[BankStatementImport]:
        result = await db.execute(
            select(BankStatementImport)
            .where(BankStatementImport.merchant_id == merchant_id)
            .order_by(BankStatementImport.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_entries_for_import(
        db: AsyncSession,
        import_id: str,
        merchant_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[BankStatementEntry]:
        result = await db.execute(
            select(BankStatementEntry)
            .where(
                BankStatementEntry.import_id == import_id,
                BankStatementEntry.merchant_id == merchant_id,
            )
            .order_by(BankStatementEntry.entry_date)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_entries(
        db: AsyncSession,
        merchant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[BankStatementEntry]:
        stmt = select(BankStatementEntry).where(BankStatementEntry.merchant_id == merchant_id)
        if date_from:
            stmt = stmt.where(BankStatementEntry.entry_date >= date_from)
        if date_to:
            stmt = stmt.where(BankStatementEntry.entry_date <= date_to)
        stmt = stmt.order_by(BankStatementEntry.entry_date.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())
