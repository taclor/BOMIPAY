import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..services.providers import ProviderAdapterRegistry
from ..services.paystack_adapter import PaystackAdapter  # noqa: F401
from ..services.transaction import TransactionService
from ..services.merchant import ProviderAccountService
from ..services.encryption import decrypt_secret
from ..services.data_source import DataSourceService

router = APIRouter()


@router.post("/webhooks/{provider_name}")
async def provider_webhook(
    provider_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    adapter = ProviderAdapterRegistry.get_adapter(provider_name)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider adapter not found")

    header_map = {k.lower(): v for k, v in request.headers.items()}
    provider_secret = None
    resolved_account = None

    for provider_account in await ProviderAccountService.get_active_provider_accounts_for_provider(db, provider_name):
        secret = decrypt_secret(provider_account.secret_encrypted)
        if adapter.verify_signature(header_map, body, secret):
            provider_secret = secret
            resolved_account = provider_account
            break

    if resolved_account is None:
        env_secret = os.getenv(f"{provider_name.upper()}_WEBHOOK_SECRET")
        if env_secret and adapter.verify_signature(header_map, body, env_secret):
            provider_secret = env_secret
            accounts = await ProviderAccountService.get_active_provider_accounts_for_provider(db, provider_name)
            if len(accounts) == 1:
                resolved_account = accounts[0]

    if resolved_account is None or not provider_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook signature or provider connection")

    try:
        normalized = adapter.process_webhook(header_map, body, provider_secret)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    transaction_data = normalized["transaction_data"]
    provider_event_id = normalized["provider_event_id"]
    event_type = normalized["event_type"]
    provider_payload = normalized["provider_payload"]

    merchant_id = str(resolved_account.merchant_id)
    await DataSourceService.upsert_webhook_source(
        db,
        merchant_id=merchant_id,
        provider_name=provider_name,
        provider_account_id=str(resolved_account.id),
    )

    await TransactionService.process_provider_event(
        db,
        provider_name=provider_name,
        provider_event_id=provider_event_id,
        event_type=event_type,
        transaction_data=transaction_data,
        provider_payload=provider_payload,
        merchant_id=merchant_id,
    )
    await db.commit()
    return {"success": True}
