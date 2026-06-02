from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.merchant import Merchant
from ..models.provider_account import ProviderAccount, ProviderAccountStatus
from ..models.user import User
from ..services.encryption import encrypt_secret, decrypt_secret


class MerchantService:
    @staticmethod
    async def get_merchant(db: AsyncSession, merchant_id):
        result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
        return result.scalars().first()

    @staticmethod
    async def create_merchant(
        db: AsyncSession,
        name: str,
        email: str,
        phone: str,
        business_type: str | None = None,
        country: str | None = None,
    ):
        merchant = Merchant(
            name=name,
            email=email,
            phone=phone,
            business_type=business_type,
            country=country,
        )
        db.add(merchant)
        await db.flush()
        await db.refresh(merchant)
        return merchant

    @staticmethod
    async def update_merchant(db: AsyncSession, merchant: Merchant, **fields):
        for key, value in fields.items():
            if value is not None and hasattr(merchant, key):
                setattr(merchant, key, value)
        await db.flush()
        await db.refresh(merchant)
        return merchant

    @staticmethod
    async def list_members(db: AsyncSession, merchant_id):
        result = await db.execute(select(User).where(User.merchant_id == merchant_id))
        return result.scalars().all()


class ProviderAccountService:
    @staticmethod
    async def create_provider_account(
        db: AsyncSession,
        merchant_id,
        provider_name: str,
        api_key: str,
        secret: str,
    ) -> ProviderAccount:
        account = ProviderAccount(
            merchant_id=merchant_id,
            provider_name=provider_name,
            api_key_encrypted=encrypt_secret(api_key),
            secret_encrypted=encrypt_secret(secret),
        )
        db.add(account)
        await db.flush()
        await db.refresh(account)
        return account

    @staticmethod
    async def list_provider_accounts(db: AsyncSession, merchant_id):
        result = await db.execute(select(ProviderAccount).where(ProviderAccount.merchant_id == merchant_id))
        return result.scalars().all()

    @staticmethod
    async def get_provider_account_for_merchant(db: AsyncSession, merchant_id, provider_name: str):
        result = await db.execute(
            select(ProviderAccount)
            .where(ProviderAccount.merchant_id == merchant_id)
            .where(ProviderAccount.provider_name == provider_name)
            .where(ProviderAccount.status == ProviderAccountStatus.active.value)
            .order_by(ProviderAccount.created_at.desc())
        )
        return result.scalars().first()

    @staticmethod
    async def get_provider_account_by_id(db: AsyncSession, account_id):
        result = await db.execute(select(ProviderAccount).where(ProviderAccount.id == account_id))
        return result.scalars().first()

    @staticmethod
    async def upsert_provider_account(
        db: AsyncSession,
        merchant_id,
        provider_name: str,
        api_key: str,
        secret: str,
    ) -> ProviderAccount:
        existing = await ProviderAccountService.get_provider_account_for_merchant(db, merchant_id, provider_name)
        if existing:
            existing.api_key_encrypted = encrypt_secret(api_key)
            existing.secret_encrypted = encrypt_secret(secret)
            existing.status = ProviderAccountStatus.active.value
            await db.flush()
            await db.refresh(existing)
            return existing

        account = ProviderAccount(
            merchant_id=merchant_id,
            provider_name=provider_name,
            api_key_encrypted=encrypt_secret(api_key),
            secret_encrypted=encrypt_secret(secret),
        )
        db.add(account)
        await db.flush()
        await db.refresh(account)
        return account

    @staticmethod
    async def disable_provider_account(db: AsyncSession, account: ProviderAccount):
        account.status = ProviderAccountStatus.inactive.value
        await db.flush()
        await db.refresh(account)
        return account

    @staticmethod
    async def get_provider_account(db: AsyncSession, account_id):
        result = await db.execute(select(ProviderAccount).where(ProviderAccount.id == account_id))
        return result.scalars().first()
