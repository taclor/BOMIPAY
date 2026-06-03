import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.bank_account import BankAccount, BankAccountVerificationStatus
from ..services.encryption import encrypt_secret, decrypt_secret

logger = logging.getLogger("bomipay")

MASK_CHAR = "*"


def mask_account_number(account_number: str) -> str:
    if len(account_number) <= 4:
        return MASK_CHAR * len(account_number)
    return MASK_CHAR * (len(account_number) - 4) + account_number[-4:]


class BankAccountService:
    @staticmethod
    async def create(
        db: AsyncSession,
        merchant_id: str,
        bank_name: str,
        account_number: str,
        account_name: str,
        currency: str = "NGN",
        purpose: str = "settlement",
        bank_code: Optional[str] = None,
        metadata_json: Optional[dict] = None,
    ) -> BankAccount:
        encrypted = encrypt_secret(account_number)
        account = BankAccount(
            id=uuid.uuid4(),
            merchant_id=merchant_id,
            bank_name=bank_name,
            bank_code=bank_code,
            account_number_encrypted=encrypted,
            account_name=account_name,
            currency=currency,
            purpose=purpose,
            metadata_json=metadata_json,
        )
        db.add(account)
        await db.flush()
        logger.info("bank_account.created", extra={"bank_account_id": str(account.id), "merchant_id": str(merchant_id)})
        return account

    @staticmethod
    async def list_for_merchant(
        db: AsyncSession,
        merchant_id: str,
        status: Optional[str] = None,
    ) -> list[BankAccount]:
        stmt = select(BankAccount).where(BankAccount.merchant_id == merchant_id)
        if status:
            stmt = stmt.where(BankAccount.status == status)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, bank_account_id: str) -> Optional[BankAccount]:
        result = await db.execute(select(BankAccount).where(BankAccount.id == bank_account_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update(
        db: AsyncSession,
        account: BankAccount,
        updates: dict,
    ) -> BankAccount:
        for field, value in updates.items():
            if value is not None and hasattr(account, field):
                setattr(account, field, value)
        await db.flush()
        return account

    @staticmethod
    async def soft_delete(db: AsyncSession, account: BankAccount) -> BankAccount:
        account.status = "archived"
        await db.flush()
        return account

    @staticmethod
    async def initiate_verification(db: AsyncSession, account: BankAccount) -> BankAccount:
        account.verification_status = BankAccountVerificationStatus.pending.value
        await db.flush()
        return account

    @staticmethod
    async def complete_verification(
        db: AsyncSession,
        account: BankAccount,
        success: bool,
    ) -> BankAccount:
        account.verification_status = (
            BankAccountVerificationStatus.verified.value
            if success
            else BankAccountVerificationStatus.failed.value
        )
        await db.flush()
        return account

    @staticmethod
    def to_response_dict(account: BankAccount) -> dict:
        try:
            raw_number = decrypt_secret(account.account_number_encrypted)
        except Exception:
            raw_number = "****"
        return {
            "id": account.id,
            "merchant_id": account.merchant_id,
            "bank_name": account.bank_name,
            "bank_code": account.bank_code,
            "account_number_masked": mask_account_number(raw_number),
            "account_name": account.account_name,
            "currency": account.currency,
            "purpose": account.purpose,
            "verification_status": account.verification_status,
            "status": account.status,
            "metadata_json": account.metadata_json,
        }
