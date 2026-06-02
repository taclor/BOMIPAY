import os
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..services.providers import ProviderAdapterRegistry
from ..services.paystack_adapter import PaystackAdapter
from ..services.transaction import TransactionService
from ..services.merchant import ProviderAccountService
from ..services.encryption import decrypt_secret

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

    normalized = adapter.normalize_webhook(body)
    transaction_data = normalized["transaction_data"]
    provider_event_id = normalized["provider_event_id"]
    event_type = normalized["event_type"]
    provider_payload = normalized["provider_payload"]

    merchant_id = transaction_data.get("merchant_id")
    if merchant_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Merchant association missing")

    provider_secret = os.getenv(f"{provider_name.upper()}_WEBHOOK_SECRET")
    if not provider_secret:
        provider_account = await ProviderAccountService.get_provider_account_for_merchant(
            db, merchant_id, provider_name
        )
        if provider_account:
            provider_secret = decrypt_secret(provider_account.secret_encrypted)

    if not adapter.verify_signature({k.lower(): v for k, v in request.headers.items()}, body, provider_secret or ""):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook signature")

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
