import pytest
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bomipay.models.ledger import LedgerAccount, JournalEntry, LedgerLine, FeeRecord
from bomipay.models.merchant import Merchant
from bomipay.services.ledger import LedgerService, UnbalancedEntryException, LedgerException


@pytest.fixture
async def merchant(db_session: AsyncSession):
    """Create a test merchant."""
    merchant = Merchant(
        name=f"TestMerchant_{uuid4()}",
        email="test@merchant.com",
        phone="+1234567890",
    )
    db_session.add(merchant)
    await db_session.flush()
    return merchant


class TestLedgerAccountManagement:
    """Test ledger account creation and retrieval."""

    @pytest.mark.asyncio
    async def test_create_account(self, db_session: AsyncSession, merchant: Merchant):
        """Create a new ledger account."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
            is_active=True,
        )

        assert account.merchant_id == merchant.id
        assert account.account_code == "MAIN"
        assert account.is_active is True

    @pytest.mark.asyncio
    async def test_get_existing_account(self, db_session: AsyncSession, merchant: Merchant):
        """Get existing account is idempotent."""
        account1 = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
            is_active=True,
        )

        account2 = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
            is_active=True,
        )

        assert account1.id == account2.id

    @pytest.mark.asyncio
    async def test_account_unique_per_merchant(self, db_session: AsyncSession):
        """Each merchant has separate accounts with same code."""
        merchant1 = Merchant(
            name=f"Merchant1_{uuid4()}",
            email="m1@test.com",
            phone="+1111111111",
        )
        merchant2 = Merchant(
            name=f"Merchant2_{uuid4()}",
            email="m2@test.com",
            phone="+2222222222",
        )
        db_session.add_all([merchant1, merchant2])
        await db_session.flush()

        account1 = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant1.id,
            account_code="MAIN",
        )

        account2 = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant2.id,
            account_code="MAIN",
        )

        assert account1.id != account2.id
        assert account1.merchant_id == merchant1.id
        assert account2.merchant_id == merchant2.id

    @pytest.mark.asyncio
    async def test_get_account_by_code(self, db_session: AsyncSession, merchant: Merchant):
        """Retrieve account by merchant + code."""
        created = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="FEE_PAYABLE",
        )

        retrieved = await LedgerService.get_account_by_code(
            db=db_session,
            merchant_id=merchant.id,
            account_code="FEE_PAYABLE",
        )

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_account_not_found(self, db_session: AsyncSession, merchant: Merchant):
        """Non-existent account returns None."""
        account = await LedgerService.get_account_by_code(
            db=db_session,
            merchant_id=merchant.id,
            account_code="NONEXISTENT",
        )

        assert account is None


class TestJournalEntryPostingAndValidation:
    """Test journal entry posting with validation."""

    @pytest.mark.asyncio
    async def test_post_balanced_entry_two_lines(self, db_session: AsyncSession, merchant: Merchant):
        """Post a balanced entry with 2 lines (simplest case)."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        entry = await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Test entry",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 1000,
                    "line_type": "DEBIT",
                    "description": "Debit line",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 1000,
                    "line_type": "CREDIT",
                    "description": "Credit line",
                },
            ],
        )

        assert entry.merchant_id == merchant.id
        assert entry.account_id == account.id
        assert len(entry.ledger_lines) == 2

    @pytest.mark.asyncio
    async def test_post_balanced_entry_multiple_lines(self, db_session: AsyncSession, merchant: Merchant):
        """Post a balanced entry with 3+ lines."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        entry = await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Multi-line entry",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 500,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 300,
                    "line_type": "CREDIT",
                },
                {
                    "account_code": "SETTLEMENT",
                    "amount_minor": 200,
                    "line_type": "CREDIT",
                },
            ],
        )

        assert len(entry.ledger_lines) == 3

    @pytest.mark.asyncio
    async def test_reject_unbalanced_entry_debit_greater(self, db_session: AsyncSession, merchant: Merchant):
        """Reject entry where debits > credits."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        with pytest.raises(UnbalancedEntryException):
            await LedgerService.post_journal_entry(
                db=db_session,
                merchant_id=merchant.id,
                account_id=account.id,
                description="Unbalanced entry",
                lines=[
                    {
                        "account_code": "MAIN",
                        "amount_minor": 2000,
                        "line_type": "DEBIT",
                    },
                    {
                        "account_code": "FEE",
                        "amount_minor": 1000,
                        "line_type": "CREDIT",
                    },
                ],
            )

    @pytest.mark.asyncio
    async def test_reject_unbalanced_entry_credit_greater(self, db_session: AsyncSession, merchant: Merchant):
        """Reject entry where credits > debits."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        with pytest.raises(UnbalancedEntryException):
            await LedgerService.post_journal_entry(
                db=db_session,
                merchant_id=merchant.id,
                account_id=account.id,
                description="Unbalanced entry",
                lines=[
                    {
                        "account_code": "MAIN",
                        "amount_minor": 500,
                        "line_type": "DEBIT",
                    },
                    {
                        "account_code": "FEE",
                        "amount_minor": 1500,
                        "line_type": "CREDIT",
                    },
                ],
            )

    @pytest.mark.asyncio
    async def test_reject_single_line_entry(self, db_session: AsyncSession, merchant: Merchant):
        """Reject entry with only 1 line (needs at least 2)."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        with pytest.raises(LedgerException):
            await LedgerService.post_journal_entry(
                db=db_session,
                merchant_id=merchant.id,
                account_id=account.id,
                description="Single line entry",
                lines=[
                    {
                        "account_code": "MAIN",
                        "amount_minor": 1000,
                        "line_type": "DEBIT",
                    },
                ],
            )

    @pytest.mark.asyncio
    async def test_reject_negative_amount(self, db_session: AsyncSession, merchant: Merchant):
        """Reject entry with negative amount."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        with pytest.raises(LedgerException):
            await LedgerService.post_journal_entry(
                db=db_session,
                merchant_id=merchant.id,
                account_id=account.id,
                description="Negative amount",
                lines=[
                    {
                        "account_code": "MAIN",
                        "amount_minor": -1000,
                        "line_type": "DEBIT",
                    },
                    {
                        "account_code": "FEE",
                        "amount_minor": -1000,
                        "line_type": "CREDIT",
                    },
                ],
            )

    @pytest.mark.asyncio
    async def test_reject_zero_amount(self, db_session: AsyncSession, merchant: Merchant):
        """Reject entry with zero amount."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        with pytest.raises(LedgerException):
            await LedgerService.post_journal_entry(
                db=db_session,
                merchant_id=merchant.id,
                account_id=account.id,
                description="Zero amount",
                lines=[
                    {
                        "account_code": "MAIN",
                        "amount_minor": 0,
                        "line_type": "DEBIT",
                    },
                    {
                        "account_code": "FEE",
                        "amount_minor": 0,
                        "line_type": "CREDIT",
                    },
                ],
            )

    @pytest.mark.asyncio
    async def test_reject_invalid_line_type(self, db_session: AsyncSession, merchant: Merchant):
        """Reject entry with invalid line_type."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        with pytest.raises(LedgerException):
            await LedgerService.post_journal_entry(
                db=db_session,
                merchant_id=merchant.id,
                account_id=account.id,
                description="Invalid line type",
                lines=[
                    {
                        "account_code": "MAIN",
                        "amount_minor": 1000,
                        "line_type": "INVALID",
                    },
                    {
                        "account_code": "FEE",
                        "amount_minor": 1000,
                        "line_type": "CREDIT",
                    },
                ],
            )


class TestIdempotency:
    """Test idempotency key handling."""

    @pytest.mark.asyncio
    async def test_idempotency_same_key_returns_existing_entry(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        """Posting with same idempotency_key returns existing entry."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        entry1 = await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Entry 1",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 1000,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 1000,
                    "line_type": "CREDIT",
                },
            ],
            idempotency_key="idempotent-key-1",
        )

        entry2 = await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Entry 2",  # Different description
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 999,  # Different amount
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 999,
                    "line_type": "CREDIT",
                },
            ],
            idempotency_key="idempotent-key-1",  # Same key
        )

        assert entry1.id == entry2.id
        assert entry1.description == "Entry 1"  # Original description preserved

    @pytest.mark.asyncio
    async def test_different_keys_create_different_entries(
        self, db_session: AsyncSession, merchant: Merchant
    ):
        """Different idempotency_keys create different entries."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        entry1 = await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Entry 1",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 1000,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 1000,
                    "line_type": "CREDIT",
                },
            ],
            idempotency_key="key-1",
        )

        entry2 = await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Entry 2",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 500,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 500,
                    "line_type": "CREDIT",
                },
            ],
            idempotency_key="key-2",
        )

        assert entry1.id != entry2.id


class TestBalanceCalculation:
    """Test account balance calculations."""

    @pytest.mark.asyncio
    async def test_balance_zero_on_empty_account(self, db_session: AsyncSession, merchant: Merchant):
        """Empty account has zero balance."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        balance = await LedgerService.get_account_balance(db=db_session, account_id=account.id)

        assert balance["debit_total_minor"] == 0
        assert balance["credit_total_minor"] == 0
        assert balance["net_balance_minor"] == 0

    @pytest.mark.asyncio
    async def test_balance_after_entry(self, db_session: AsyncSession, merchant: Merchant):
        """Balance updates after posting entry."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Entry 1",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 1000,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 1000,
                    "line_type": "CREDIT",
                },
            ],
        )

        balance = await LedgerService.get_account_balance(db=db_session, account_id=account.id)

        assert balance["debit_total_minor"] == 1000
        assert balance["credit_total_minor"] == 1000
        assert balance["net_balance_minor"] == 0

    @pytest.mark.asyncio
    async def test_balance_cumulative_multiple_entries(self, db_session: AsyncSession, merchant: Merchant):
        """Balance accumulates across multiple entries."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        # Entry 1: 1000 debit, 1000 credit
        await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Entry 1",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 1000,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 1000,
                    "line_type": "CREDIT",
                },
            ],
        )

        # Entry 2: 500 debit, 500 credit
        await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Entry 2",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 500,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 500,
                    "line_type": "CREDIT",
                },
            ],
        )

        balance = await LedgerService.get_account_balance(db=db_session, account_id=account.id)

        assert balance["debit_total_minor"] == 1500
        assert balance["credit_total_minor"] == 1500
        assert balance["net_balance_minor"] == 0


class TestTenantIsolation:
    """Test that ledger data is isolated per merchant."""

    @pytest.mark.asyncio
    async def test_entries_isolated_by_merchant(self, db_session: AsyncSession):
        """Entries from one merchant don't affect another."""
        merchant1 = Merchant(
            name=f"M1_{uuid4()}",
            email="m1@test.com",
            phone="+1111111111",
        )
        merchant2 = Merchant(
            name=f"M2_{uuid4()}",
            email="m2@test.com",
            phone="+2222222222",
        )
        db_session.add_all([merchant1, merchant2])
        await db_session.flush()

        account1 = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant1.id,
            account_code="MAIN",
        )

        account2 = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant2.id,
            account_code="MAIN",
        )

        # Post entry for merchant1
        await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant1.id,
            account_id=account1.id,
            description="M1 entry",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 1000,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 1000,
                    "line_type": "CREDIT",
                },
            ],
        )

        # Get entries for each merchant
        entries1 = await LedgerService.get_journal_entries(
            db=db_session,
            merchant_id=merchant1.id,
        )

        entries2 = await LedgerService.get_journal_entries(
            db=db_session,
            merchant_id=merchant2.id,
        )

        assert len(entries1) == 1
        assert len(entries2) == 0

    @pytest.mark.asyncio
    async def test_balance_isolated_by_merchant(self, db_session: AsyncSession):
        """Account balances are isolated per merchant."""
        merchant1 = Merchant(
            name=f"M1_{uuid4()}",
            email="m1@test.com",
            phone="+1111111111",
        )
        merchant2 = Merchant(
            name=f"M2_{uuid4()}",
            email="m2@test.com",
            phone="+2222222222",
        )
        db_session.add_all([merchant1, merchant2])
        await db_session.flush()

        account1 = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant1.id,
            account_code="MAIN",
        )

        account2 = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant2.id,
            account_code="MAIN",
        )

        # Only post entry for merchant1
        await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant1.id,
            account_id=account1.id,
            description="M1 entry",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 5000,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 5000,
                    "line_type": "CREDIT",
                },
            ],
        )

        balance1 = await LedgerService.get_account_balance(
            db=db_session,
            account_id=account1.id,
        )

        balance2 = await LedgerService.get_account_balance(
            db=db_session,
            account_id=account2.id,
        )

        assert balance1["debit_total_minor"] == 5000
        assert balance2["debit_total_minor"] == 0


class TestFeeRecording:
    """Test immutable fee record functionality."""

    @pytest.mark.asyncio
    async def test_record_fee(self, db_session: AsyncSession, merchant: Merchant):
        """Record a fee in the audit trail."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        entry = await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Entry with fee",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 100,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 100,
                    "line_type": "CREDIT",
                },
            ],
        )

        fee = await LedgerService.record_fee(
            db=db_session,
            merchant_id=merchant.id,
            journal_entry_id=entry.id,
            fee_type="TRANSACTION_FEE",
            amount_minor=50,
            description="Transaction fee 0.5%",
        )

        assert fee.merchant_id == merchant.id
        assert fee.journal_entry_id == entry.id
        assert fee.fee_type == "TRANSACTION_FEE"
        assert fee.amount_minor == 50

    @pytest.mark.asyncio
    async def test_reject_negative_fee(self, db_session: AsyncSession, merchant: Merchant):
        """Reject negative fee amount."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        entry = await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Entry",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 100,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 100,
                    "line_type": "CREDIT",
                },
            ],
        )

        with pytest.raises(LedgerException):
            await LedgerService.record_fee(
                db=db_session,
                merchant_id=merchant.id,
                journal_entry_id=entry.id,
                fee_type="TRANSACTION_FEE",
                amount_minor=-50,
            )

    @pytest.mark.asyncio
    async def test_get_fees_for_merchant(self, db_session: AsyncSession, merchant: Merchant):
        """List all fees for a merchant."""
        account = await LedgerService.get_or_create_account(
            db=db_session,
            merchant_id=merchant.id,
            account_code="MAIN",
        )

        entry = await LedgerService.post_journal_entry(
            db=db_session,
            merchant_id=merchant.id,
            account_id=account.id,
            description="Entry",
            lines=[
                {
                    "account_code": "MAIN",
                    "amount_minor": 100,
                    "line_type": "DEBIT",
                },
                {
                    "account_code": "FEE",
                    "amount_minor": 100,
                    "line_type": "CREDIT",
                },
            ],
        )

        await LedgerService.record_fee(
            db=db_session,
            merchant_id=merchant.id,
            journal_entry_id=entry.id,
            fee_type="TRANSACTION_FEE",
            amount_minor=10,
        )

        await LedgerService.record_fee(
            db=db_session,
            merchant_id=merchant.id,
            journal_entry_id=entry.id,
            fee_type="SETTLEMENT_FEE",
            amount_minor=5,
        )

        fees = await LedgerService.get_fees(db=db_session, merchant_id=merchant.id)

        assert len(fees) == 2
        assert fees[0].fee_type == "TRANSACTION_FEE"
        assert fees[1].fee_type == "SETTLEMENT_FEE"
