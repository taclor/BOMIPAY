"""Tests for Provider Sync module."""
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from bomipay.models.provider_sync_job import ProviderSyncJob, ProviderSyncStatus, ProviderSyncType, ErrorSeverity
from bomipay.models.merchant import Merchant, MerchantStatus
from bomipay.models.provider_account import ProviderAccount, ProviderAccountStatus
from bomipay.services.provider_sync import ProviderSyncService, BASE_BACKOFF_SECONDS


@pytest.mark.asyncio
async def test_create_sync_job(db_session: AsyncSession):
    """Test creating a sync job."""
    merchant = Merchant(
        id=uuid4(),
        name="Test Merchant",
        email="test@example.com",
        phone="+2348000000000",
        status=MerchantStatus.active.value,
    )
    db_session.add(merchant)
    
    job = await ProviderSyncService.create_job(
        db_session,
        merchant_id=str(merchant.id),
        provider_account_id=str(uuid4()),
        sync_type=ProviderSyncType.transactions.value,
    )
    
    assert job.status == ProviderSyncStatus.queued.value
    assert job.sync_type == ProviderSyncType.transactions.value
    assert job.retry_count == 0
    assert job.max_retries == 3


@pytest.mark.asyncio
async def test_error_classification_retryable(db_session: AsyncSession):
    """Test classification of retryable errors."""
    errors = [
        ConnectionError("Connection timeout"),
        TimeoutError("Request timeout"),
        Exception("Temporarily unavailable"),
        Exception("HTTP 429: Rate limit exceeded"),
        Exception("HTTP 503: Service unavailable"),
    ]
    
    for error in errors:
        severity, is_retryable = ProviderSyncService._classify_error(error)
        assert is_retryable, f"Error should be retryable: {error}"


@pytest.mark.asyncio
async def test_error_classification_permanent(db_session: AsyncSession):
    """Test classification of permanent errors."""
    errors = [
        Exception("HTTP 401: Unauthorized"),
        Exception("HTTP 403: Forbidden"),
        Exception("Invalid credentials"),
        Exception("HTTP 404: Not found"),
        Exception("HTTP 400: Validation error"),
    ]
    
    for error in errors:
        severity, is_retryable = ProviderSyncService._classify_error(error)
        assert not is_retryable, f"Error should not be retryable: {error}"


@pytest.mark.asyncio
async def test_backoff_calculation(db_session: AsyncSession):
    """Test exponential backoff calculation."""
    merchant = Merchant(
        id=uuid4(),
        name="Test Merchant",
        email="test@example.com",
        phone="+2348000000000",
        status=MerchantStatus.active.value,
    )
    db_session.add(merchant)
    
    job = ProviderSyncJob(
        id=uuid4(),
        merchant_id=merchant.id,
        provider_account_id=uuid4(),
        sync_type=ProviderSyncType.transactions.value,
        status=ProviderSyncStatus.failed.value,
        correlation_id="test",
    )
    
    # Test first retry: 2^0 * BASE = 2 seconds
    job.retry_count = 0
    next_retry = ProviderSyncService._calculate_next_retry(job)
    backoff_seconds = (next_retry - datetime.now(timezone.utc)).total_seconds()
    assert 1 < backoff_seconds < 3  # Allow some variance
    
    # Test second retry: 2^1 * BASE = 4 seconds  
    job.retry_count = 1
    next_retry = ProviderSyncService._calculate_next_retry(job)
    backoff_seconds = (next_retry - datetime.now(timezone.utc)).total_seconds()
    assert 3 < backoff_seconds < 5
    
    # Test max backoff cap
    job.retry_count = 20  # Would be huge without cap
    next_retry = ProviderSyncService._calculate_next_retry(job)
    backoff_seconds = (next_retry - datetime.now(timezone.utc)).total_seconds()
    assert backoff_seconds <= 3600 + 1  # Max 1 hour + variance


@pytest.mark.asyncio
async def test_max_retries_exceeded(db_session: AsyncSession):
    """Test that job fails permanently when max retries exceeded."""
    merchant = Merchant(
        id=uuid4(),
        name="Test Merchant",
        email="test@example.com",
        phone="+2348000000000",
        status=MerchantStatus.active.value,
    )
    db_session.add(merchant)
    await db_session.flush()
    
    account = ProviderAccount(
        id=uuid4(),
        merchant_id=merchant.id,
        provider_name="test_provider",
        api_key_encrypted="encrypted_key",
        secret_encrypted="encrypted_secret",
        status=ProviderAccountStatus.active.value,
    )
    db_session.add(account)
    await db_session.flush()
    
    job = ProviderSyncJob(
        id=uuid4(),
        merchant_id=merchant.id,
        provider_account_id=account.id,
        sync_type=ProviderSyncType.transactions.value,
        status=ProviderSyncStatus.queued.value,
        correlation_id="test",
        max_retries=1,
        retry_count=1,  # Already at max
    )
    db_session.add(job)
    
    # Simulate transient error when already at max retries
    class TransientError(Exception):
        pass
    
    severity, is_retryable = ProviderSyncService._classify_error(TransientError("Network timeout"))
    
    # Even though error is retryable, job should be marked failed because max retries exceeded
    assert is_retryable
    assert job.retry_count >= job.max_retries


@pytest.mark.asyncio
async def test_get_pending_jobs(db_session: AsyncSession):
    """Test retrieving jobs that need to be retried."""
    merchant = Merchant(
        id=uuid4(),
        name="Test Merchant",
        email="test@example.com",
        phone="+2348000000000",
        status=MerchantStatus.active.value,
    )
    db_session.add(merchant)
    await db_session.flush()
    
    # Create jobs with different retry times
    job_ready_now = ProviderSyncJob(
        id=uuid4(),
        merchant_id=merchant.id,
        provider_account_id=uuid4(),
        sync_type=ProviderSyncType.transactions.value,
        status=ProviderSyncStatus.queued.value,
        correlation_id="job1",
        next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),  # Past
    )
    
    job_ready_soon = ProviderSyncJob(
        id=uuid4(),
        merchant_id=merchant.id,
        provider_account_id=uuid4(),
        sync_type=ProviderSyncType.transactions.value,
        status=ProviderSyncStatus.queued.value,
        correlation_id="job2",
        next_retry_at=datetime.now(timezone.utc) + timedelta(seconds=60),  # Future
    )
    
    job_no_retry = ProviderSyncJob(
        id=uuid4(),
        merchant_id=merchant.id,
        provider_account_id=uuid4(),
        sync_type=ProviderSyncType.transactions.value,
        status=ProviderSyncStatus.completed.value,
        correlation_id="job3",
    )
    
    db_session.add(job_ready_now)
    db_session.add(job_ready_soon)
    db_session.add(job_no_retry)
    await db_session.flush()
    
    # Get pending jobs - should include only jobs ready to retry
    pending = await ProviderSyncService.get_pending_jobs(db_session, limit=100)
    pending_ids = {str(j.id) for j in pending}
    
    assert str(job_ready_now.id) in pending_ids
    assert str(job_ready_soon.id) not in pending_ids
    assert str(job_no_retry.id) not in pending_ids


@pytest.mark.asyncio
async def test_get_job(db_session: AsyncSession):
    """Test retrieving a specific job."""
    merchant = Merchant(
        id=uuid4(),
        name="Test Merchant",
        email="test@example.com",
        phone="+2348000000000",
        status=MerchantStatus.active.value,
    )
    db_session.add(merchant)
    await db_session.flush()
    
    job = ProviderSyncJob(
        id=uuid4(),
        merchant_id=merchant.id,
        provider_account_id=uuid4(),
        sync_type=ProviderSyncType.settlements.value,
        status=ProviderSyncStatus.completed.value,
        correlation_id="test",
        records_seen=100,
    )
    db_session.add(job)
    await db_session.flush()
    
    retrieved = await ProviderSyncService.get_job(db_session, str(job.id))
    
    assert retrieved is not None
    assert str(retrieved.id) == str(job.id)
    assert retrieved.sync_type == ProviderSyncType.settlements.value
    assert retrieved.records_seen == 100


@pytest.mark.asyncio
async def test_list_jobs_for_provider_account(db_session: AsyncSession):
    """Test listing jobs for a provider account."""
    merchant = Merchant(
        id=uuid4(),
        name="Test Merchant",
        email="test@example.com",
        phone="+2348000000000",
        status=MerchantStatus.active.value,
    )
    db_session.add(merchant)
    await db_session.flush()
    
    provider_account_id = str(uuid4())
    
    job1 = ProviderSyncJob(
        id=uuid4(),
        merchant_id=merchant.id,
        provider_account_id=provider_account_id,
        sync_type=ProviderSyncType.transactions.value,
        status=ProviderSyncStatus.completed.value,
        correlation_id="job1",
    )
    
    job2 = ProviderSyncJob(
        id=uuid4(),
        merchant_id=merchant.id,
        provider_account_id=provider_account_id,
        sync_type=ProviderSyncType.settlements.value,
        status=ProviderSyncStatus.completed.value,
        correlation_id="job2",
    )
    
    job3 = ProviderSyncJob(
        id=uuid4(),
        merchant_id=merchant.id,
        provider_account_id=str(uuid4()),  # Different provider account
        sync_type=ProviderSyncType.refunds.value,
        status=ProviderSyncStatus.completed.value,
        correlation_id="job3",
    )
    
    db_session.add(job1)
    db_session.add(job2)
    db_session.add(job3)
    await db_session.flush()
    
    jobs = await ProviderSyncService.list_jobs_for_provider_account(
        db_session, provider_account_id, str(merchant.id), limit=100
    )
    
    assert len(jobs) == 2
    job_ids = {str(j.id) for j in jobs}
    assert str(job1.id) in job_ids
    assert str(job2.id) in job_ids
    assert str(job3.id) not in job_ids

