import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .security import hash_password
from ..models.user import Role, User
from ..models.merchant import Merchant


class UserService:
    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    @staticmethod
    async def create_user(
        db: AsyncSession,
        email: str,
        password: str,
        full_name: str,
        phone: str,
        role: Role = Role.merchant_user,
        merchant_id: uuid.UUID | None = None,
    ) -> User:
        hashed_password = hash_password(password)
        user = User(
            email=email,
            full_name=full_name,
            phone=phone,
            hashed_password=hashed_password,
            role=role,
            merchant_id=merchant_id,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def create_merchant_for_user(
        db: AsyncSession,
        merchant_name: str,
        email: str,
        phone: str,
        business_type: str | None = None,
        country: str | None = None,
    ) -> Merchant:
        merchant = Merchant(
            name=merchant_name,
            email=email,
            phone=phone,
            business_type=business_type,
            country=country,
        )
        db.add(merchant)
        await db.flush()
        await db.refresh(merchant)
        return merchant
