from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.user import Role
from ..schemas.provider import (
    ProviderAccountData,
    ProviderConnectRequest,
    ProviderConnectResponse,
    ProviderHealthResponse,
    ProviderListResponse,
    ProviderTestRequest,
    ProviderTestResponse,
)
from ..services.auth import get_current_active_user, require_role
from ..services.audit import log_audit_event
from ..services.encryption import decrypt_secret
from ..services.merchant import ProviderAccountService
from ..services.providers import ProviderAdapterRegistry
from ..services.data_source import DataSourceService

router = APIRouter()


@router.post("/providers/test-connection", response_model=ProviderTestResponse)
async def test_connection(
    payload: ProviderTestRequest,
    current_user=Depends(get_current_active_user),
) -> ProviderTestResponse:
    adapter = ProviderAdapterRegistry.get_adapter(payload.provider_name)
    if adapter is None:
        return ProviderTestResponse(success=False, message="Unsupported provider")

    credentials = {
        "api_key": payload.public_key,
        "secret_key": payload.secret_key,
    }
    try:
        is_valid = adapter.connect_account(credentials)
        if is_valid:
            return ProviderTestResponse(success=True, message="Connection successful")
        else:
            return ProviderTestResponse(success=False, message="Invalid credentials")
    except Exception as e:
        return ProviderTestResponse(success=False, message=str(e))


@router.post("/providers/connect", response_model=ProviderConnectResponse)
async def connect_provider(
    payload: ProviderConnectRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProviderConnectResponse:
    merchant_id = payload.merchant_id or current_user.merchant_id
    if merchant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="merchant_id is required",
        )
    if current_user.role != Role.admin and str(current_user.merchant_id) != merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    adapter = ProviderAdapterRegistry.get_adapter(payload.provider_name)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider")

    credentials = {
        "api_key": payload.credentials.api_key,
        "secret_key": payload.credentials.secret_key,
    }
    if not adapter.connect_account(credentials):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid provider credentials")

    account = await ProviderAccountService.upsert_provider_account(
        db,
        merchant_id=merchant_id,
        provider_name=payload.provider_name,
        api_key=payload.credentials.api_key,
        secret=payload.credentials.secret_key,
    )
    await DataSourceService.upsert_provider_api_source(
        db,
        merchant_id=str(merchant_id),
        provider_name=payload.provider_name,
        provider_account_id=str(account.id),
    )
    log_audit_event(
        db,
        event_type="provider.connect",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={
            "merchant_id": str(merchant_id),
            "provider_name": payload.provider_name,
            "provider_account_id": str(account.id),
        },
    )
    await db.commit()
    return ProviderConnectResponse(
        success=True,
        data=ProviderAccountData(
            provider_account_id=str(account.id),
            provider_name=account.provider_name,
            status=account.status,
        ),
    )


@router.get("/providers", response_model=list[ProviderListResponse])
async def list_providers(
    merchant_id: str | None = None,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProviderListResponse]:
    effective_merchant_id = merchant_id or current_user.merchant_id
    if effective_merchant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="merchant_id is required",
        )
    if current_user.role != Role.admin and str(current_user.merchant_id) != effective_merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    accounts = await ProviderAccountService.list_provider_accounts(db, effective_merchant_id)
    return [ProviderListResponse(
        provider_account_id=str(account.id),
        provider_name=account.provider_name,
        merchant_id=str(account.merchant_id),
        status=account.status,
    ) for account in accounts]


@router.get("/providers/{provider_name}/health", response_model=ProviderHealthResponse)
async def provider_health(
    provider_name: str,
    merchant_id: str | None = None,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProviderHealthResponse:
    effective_merchant_id = merchant_id or current_user.merchant_id
    if effective_merchant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="merchant_id is required",
        )
    if current_user.role != Role.admin and str(current_user.merchant_id) != effective_merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    account = await ProviderAccountService.get_provider_account_for_merchant(db, effective_merchant_id, provider_name)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider account not found")

    adapter = ProviderAdapterRegistry.get_adapter(provider_name)
    provider_health = {"connected": False, "status": account.status}
    if adapter:
        provider_health = adapter.get_provider_health({
            "api_key": decrypt_secret(account.api_key_encrypted),
            "secret_key": decrypt_secret(account.secret_encrypted),
        })

    return ProviderHealthResponse(
        provider_name=account.provider_name,
        merchant_id=str(account.merchant_id),
        status=provider_health.get("status", account.status),
        connected=provider_health.get("connected", account.status == "active"),
    )


@router.delete("/providers/{provider_account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_account(
    provider_account_id: str,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    account = await ProviderAccountService.get_provider_account_by_id(db, provider_account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider account not found")
    if current_user.role != Role.admin and current_user.merchant_id != account.merchant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    await ProviderAccountService.disable_provider_account(db, account)
    log_audit_event(
        db,
        event_type="provider.disconnect",
        actor_id=str(current_user.id),
        actor_role=current_user.role.value,
        event_payload={
            "provider_account_id": str(account.id),
            "merchant_id": str(account.merchant_id),
        },
    )
    await db.commit()
    return None
