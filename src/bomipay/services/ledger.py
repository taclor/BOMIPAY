from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..models.ledger import LedgerAccount, JournalEntry, LedgerLine, FeeRecord


class LedgerException(Exception):
    """Base exception for ledger operations."""
    pass


class UnbalancedEntryException(LedgerException):
    """Entry debit total does not equal credit total."""
    pass


class LedgerService:
    """Service for immutable double-entry bookkeeping operations."""

    @staticmethod
    async def get_or_create_account(
        db: AsyncSession,
        merchant_id: UUID,
        account_code: str,
        is_active: bool = True,
    ) -> LedgerAccount:
        """Get existing account or create new one. Idempotent."""
        result = await db.execute(
            select(LedgerAccount).where(
                and_(
                    LedgerAccount.merchant_id == merchant_id,
                    LedgerAccount.account_code == account_code,
                )
            )
        )
        account = result.scalars().first()
        
        if account:
            return account
        
        account = LedgerAccount(
            merchant_id=merchant_id,
            account_code=account_code,
            is_active=is_active,
        )
        db.add(account)
        await db.flush()
        return account

    @staticmethod
    async def post_journal_entry(
        db: AsyncSession,
        merchant_id: UUID,
        account_id: UUID,
        description: str,
        lines: list[dict],  # [{"account_code": str, "amount_minor": int, "line_type": "DEBIT"|"CREDIT", "description": str?}, ...]
        idempotency_key: Optional[str] = None,
        transaction_id: Optional[UUID] = None,
    ) -> JournalEntry:
        """
        Post a balanced journal entry with 2+ lines (double-entry bookkeeping).
        
        Validates:
        - At least 2 lines
        - Debit total == Credit total
        - All amounts positive (BigInteger)
        - line_type is DEBIT or CREDIT
        
        If idempotency_key provided and already exists, returns existing entry.
        
        Raises:
        - UnbalancedEntryException if debits != credits
        - LedgerException for other validation errors
        """
        
        # Check idempotency
        if idempotency_key:
            result = await db.execute(
                select(JournalEntry)
                .options(selectinload(JournalEntry.ledger_lines))
                .where(JournalEntry.idempotency_key == idempotency_key)
            )
            existing = result.scalars().first()
            if existing:
                return existing
        
        # Validate entry structure
        if not lines or len(lines) < 2:
            raise LedgerException("Journal entry must have at least 2 lines (double-entry)")
        
        # Validate line types
        debits = 0
        credits = 0
        
        for line in lines:
            if line.get("line_type") not in ("DEBIT", "CREDIT"):
                raise LedgerException(f"Invalid line_type: {line.get('line_type')}, must be DEBIT or CREDIT")
            
            if line.get("amount_minor", 0) <= 0:
                raise LedgerException(f"amount_minor must be > 0, got {line.get('amount_minor')}")
            
            if line.get("line_type") == "DEBIT":
                debits += line.get("amount_minor")
            else:
                credits += line.get("amount_minor")
        
        # Validate balanced entry
        if debits != credits:
            raise UnbalancedEntryException(
                f"Journal entry unbalanced: debits={debits}, credits={credits}"
            )
        
        # Create entry
        entry = JournalEntry(
            merchant_id=merchant_id,
            account_id=account_id,
            description=description,
            idempotency_key=idempotency_key,
            transaction_id=transaction_id,
        )
        db.add(entry)
        await db.flush()
        
        # Add lines
        for line_data in lines:
            line = LedgerLine(
                journal_entry_id=entry.id,
                account_code=line_data.get("account_code"),
                amount_minor=line_data.get("amount_minor"),
                line_type=line_data.get("line_type"),
                description=line_data.get("description"),
            )
            db.add(line)
        
        await db.flush()
        
        # Refetch with eager-loaded relationships
        result = await db.execute(
            select(JournalEntry)
            .options(selectinload(JournalEntry.ledger_lines))
            .where(JournalEntry.id == entry.id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_account_balance(
        db: AsyncSession,
        account_id: UUID,
    ) -> dict:
        """
        Calculate current balance for account.
        
        Returns: {"account_id": UUID, "debit_total_minor": int, "credit_total_minor": int, "net_balance_minor": int}
        """
        result = await db.execute(
            select(
                func.sum(
                    case(
                        (LedgerLine.line_type == "DEBIT", LedgerLine.amount_minor),
                        else_=0
                    )
                ).label("debit_total"),
                func.sum(
                    case(
                        (LedgerLine.line_type == "CREDIT", LedgerLine.amount_minor),
                        else_=0
                    )
                ).label("credit_total"),
            ).select_from(LedgerLine)
            .join(JournalEntry, LedgerLine.journal_entry_id == JournalEntry.id)
            .where(JournalEntry.account_id == account_id)
        )
        
        row = result.first()
        debit_total = row[0] or 0
        credit_total = row[1] or 0
        
        return {
            "account_id": str(account_id),
            "debit_total_minor": debit_total,
            "credit_total_minor": credit_total,
            "net_balance_minor": debit_total - credit_total,  # Debit positive, credit negative
        }

    @staticmethod
    async def record_fee(
        db: AsyncSession,
        merchant_id: UUID,
        journal_entry_id: UUID,
        fee_type: str,
        amount_minor: int,
        description: Optional[str] = None,
    ) -> FeeRecord:
        """Record immutable fee in audit trail."""
        if amount_minor <= 0:
            raise LedgerException("Fee amount_minor must be > 0")
        
        fee = FeeRecord(
            merchant_id=merchant_id,
            journal_entry_id=journal_entry_id,
            fee_type=fee_type,
            amount_minor=amount_minor,
            description=description,
        )
        db.add(fee)
        await db.flush()
        return fee

    @staticmethod
    async def get_account_by_code(
        db: AsyncSession,
        merchant_id: UUID,
        account_code: str,
    ) -> Optional[LedgerAccount]:
        """Retrieve account by merchant + code."""
        result = await db.execute(
            select(LedgerAccount).where(
                and_(
                    LedgerAccount.merchant_id == merchant_id,
                    LedgerAccount.account_code == account_code,
                )
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_journal_entries(
        db: AsyncSession,
        merchant_id: UUID,
        account_id: Optional[UUID] = None,
    ) -> list[JournalEntry]:
        """List journal entries for merchant, optionally filtered by account."""
        query = select(JournalEntry).options(selectinload(JournalEntry.ledger_lines)).where(JournalEntry.merchant_id == merchant_id)
        if account_id:
            query = query.where(JournalEntry.account_id == account_id)
        
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_fees(
        db: AsyncSession,
        merchant_id: UUID,
    ) -> list[FeeRecord]:
        """List all fee records for merchant."""
        result = await db.execute(
            select(FeeRecord).where(FeeRecord.merchant_id == merchant_id)
        )
        return result.scalars().all()
