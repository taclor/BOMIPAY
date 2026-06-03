from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.alert import AlertSeverity, AlertType
from ..models.transaction import Transaction, TransactionStatus
from ..models.transaction_event import TransactionEvent
from .alert import AlertService


class TransactionService:
    @staticmethod
    async def get_event_by_provider_id(
        db: AsyncSession, provider_name: str, provider_event_id: str
    ) -> TransactionEvent | None:
        result = await db.execute(
            select(TransactionEvent)
            .options(selectinload(TransactionEvent.transaction))
            .where(TransactionEvent.provider_name == provider_name)
            .where(TransactionEvent.provider_event_id == provider_event_id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_transaction_by_provider_reference(
        db: AsyncSession, provider_name: str, provider_transaction_id: str
    ) -> Transaction | None:
        result = await db.execute(
            select(Transaction)
            .where(Transaction.provider_name == provider_name)
            .where(Transaction.provider_transaction_id == provider_transaction_id)
        )
        return result.scalars().first()

    @staticmethod
    async def process_provider_event(
        db: AsyncSession,
        provider_name: str,
        provider_event_id: str,
        event_type: str,
        transaction_data: dict,
        provider_payload: dict,
        merchant_id,
    ) -> Transaction:
        existing_event = await TransactionService.get_event_by_provider_id(
            db, provider_name, provider_event_id
        )
        if existing_event:
            return existing_event.transaction

        transaction = await TransactionService.get_transaction_by_provider_reference(
            db, provider_name, transaction_data["provider_transaction_id"]
        )
        if not transaction:
            transaction = Transaction(
                merchant_id=merchant_id,
                provider_name=provider_name,
                provider_transaction_id=transaction_data["provider_transaction_id"],
                internal_reference=transaction_data.get("internal_reference"),
                external_reference=transaction_data.get("external_reference"),
                payment_type=transaction_data.get("payment_type"),
                payment_channel=transaction_data.get("payment_channel"),
                currency=transaction_data["currency"],
                amount=transaction_data["amount"],
                fee_amount=transaction_data.get("fee_amount", 0),
                net_amount=transaction_data.get("net_amount"),
                status=transaction_data.get("status", TransactionStatus.pending.value),
                status_reason=transaction_data.get("status_reason"),
                initiated_at=transaction_data.get("initiated_at"),
                confirmed_at=transaction_data.get("confirmed_at"),
                settled_at=transaction_data.get("settled_at"),
                customer_name=transaction_data.get("customer_name"),
                customer_email=transaction_data.get("customer_email"),
                customer_phone=transaction_data.get("customer_phone"),
                metadata_json=transaction_data.get("metadata_json"),
            )
            db.add(transaction)
            await db.flush()
        else:
            for key, value in transaction_data.items():
                if key in {
                    "internal_reference",
                    "external_reference",
                    "payment_type",
                    "payment_channel",
                    "currency",
                    "amount",
                    "fee_amount",
                    "net_amount",
                    "status",
                    "status_reason",
                    "initiated_at",
                    "confirmed_at",
                    "settled_at",
                    "customer_name",
                    "customer_email",
                    "customer_phone",
                    "metadata_json",
                }:
                    if value is not None:
                        setattr(transaction, key, value)
            await db.flush()

        event = TransactionEvent(
            transaction_id=transaction.id,
            provider_name=provider_name,
            provider_event_id=provider_event_id,
            event_type=event_type,
            provider_payload=provider_payload,
            status=transaction_data.get("status"),
        )
        db.add(event)
        await db.flush()

        if transaction_data.get("status") == TransactionStatus.failed.value:
            await AlertService.create_alert(
                db=db,
                merchant_id=merchant_id,
                transaction_id=transaction.id,
                source_event_id=provider_event_id,
                alert_type=AlertType.provider_error,
                severity=AlertSeverity.high,
                description=f"Transaction {transaction.provider_transaction_id} failed on {provider_name}.",
                metadata_json={
                    "provider_name": provider_name,
                    "provider_transaction_id": transaction.provider_transaction_id,
                    "failure_reason": transaction.status_reason,
                },
            )

        await db.refresh(transaction)
        return transaction
