import json
import logging
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from ..config import settings

logger = logging.getLogger("bomipay.cache")


class CacheLayer:
    """High-level cache abstraction for performance-critical operations.
    
    Manages caching for:
    - Provider health metrics (1 hour TTL)
    - Merchant dashboards (5 minute TTL)
    - Provider sync status (15 minute TTL)
    - Reconciliation status (10 minute TTL)
    """
    
    _redis_client: Optional[redis.Redis] = None
    
    PROVIDER_HEALTH_TTL = 3600  # 1 hour
    DASHBOARD_TTL = 300  # 5 minutes
    PROVIDER_SYNC_TTL = 900  # 15 minutes
    RECONCILIATION_TTL = 600  # 10 minutes
    
    @classmethod
    async def initialize(cls) -> None:
        """Initialize Redis connection pool."""
        if cls._redis_client is None:
            try:
                cls._redis_client = await redis.from_url(
                    settings.redis_url,
                    encoding="utf8",
                    decode_responses=True,
                    socket_keepalive=True,
                    socket_keepalive_options={
                        1: 1,  # TCP_KEEPIDLE
                        2: 1,  # TCP_KEEPINTVL
                        3: 3,  # TCP_KEEPCNT
                    } if hasattr(redis, 'SO_KEEPALIVE') else {},
                )
                logger.info("Cache layer initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis: {e}")
                cls._redis_client = None
    
    @classmethod
    async def close(cls) -> None:
        """Close Redis connection."""
        if cls._redis_client:
            await cls._redis_client.close()
            cls._redis_client = None
            logger.info("Cache layer closed")
    
    @classmethod
    async def get_client(cls) -> Optional[redis.Redis]:
        """Get Redis client, initializing if needed."""
        if cls._redis_client is None:
            await cls.initialize()
        return cls._redis_client
    
    @classmethod
    def _make_key(cls, namespace: str, *parts: str) -> str:
        """Create a cache key from namespace and parts."""
        key_parts = [namespace] + list(parts)
        return ":".join(str(p) for p in key_parts)
    
    @classmethod
    async def get(cls, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            client = await cls.get_client()
            if not client:
                return None
            value = await client.get(key)
            if value:
                logger.debug(f"Cache hit: {key}")
                return json.loads(value)
            logger.debug(f"Cache miss: {key}")
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
    
    @classmethod
    async def set(cls, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL."""
        try:
            client = await cls.get_client()
            if not client:
                return False
            await client.setex(key, ttl, json.dumps(value))
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False
    
    @classmethod
    async def delete(cls, key: str) -> bool:
        """Delete key from cache."""
        try:
            client = await cls.get_client()
            if not client:
                return False
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False
    
    @classmethod
    async def delete_pattern(cls, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        try:
            client = await cls.get_client()
            if not client:
                return 0
            keys = await client.keys(pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete pattern error: {e}")
            return 0
    
    @classmethod
    async def get_or_compute(
        cls,
        key: str,
        compute_fn,
        ttl: int = 3600,
        *args,
        **kwargs
    ) -> Any:
        """Get from cache or compute and cache."""
        try:
            cached = await cls.get(key)
            if cached is not None:
                return cached
        except Exception:
            pass
        
        # Compute value
        if len(args) > 0 and isinstance(args[0], AsyncSession):
            value = await compute_fn(*args, **kwargs)
        else:
            value = await compute_fn(*args, **kwargs)
        
        # Cache it
        try:
            await cls.set(key, value, ttl)
        except Exception as e:
            logger.warning(f"Failed to cache computed value: {e}")
        
        return value
    
    # === Provider Health Caching ===
    
    @classmethod
    async def get_provider_health_cached(
        cls,
        merchant_id: str,
        provider_name: str,
        compute_fn,
    ) -> Dict[str, Any]:
        """Get provider health (cached for 1 hour).
        
        Args:
            merchant_id: Merchant ID
            provider_name: Provider name (e.g., 'paystack', 'flutterwave')
            compute_fn: Async function to compute health if not cached
        
        Returns:
            Provider health dict
        """
        key = cls._make_key("health", merchant_id, provider_name)
        return await cls.get_or_compute(key, compute_fn, cls.PROVIDER_HEALTH_TTL)
    
    @classmethod
    async def invalidate_provider_health(cls, merchant_id: str) -> int:
        """Invalidate all health metrics for a merchant."""
        pattern = cls._make_key("health", merchant_id, "*")
        return await cls.delete_pattern(pattern)
    
    # === Dashboard Caching ===
    
    @classmethod
    async def get_dashboard_cached(
        cls,
        merchant_id: str,
        compute_fn,
    ) -> Dict[str, Any]:
        """Get merchant dashboard (cached for 5 minutes).
        
        Args:
            merchant_id: Merchant ID
            compute_fn: Async function to compute dashboard if not cached
        
        Returns:
            Dashboard data dict
        """
        key = cls._make_key("dashboard", merchant_id)
        return await cls.get_or_compute(key, compute_fn, cls.DASHBOARD_TTL)
    
    @classmethod
    async def invalidate_dashboard(cls, merchant_id: str) -> bool:
        """Invalidate dashboard cache for a merchant."""
        key = cls._make_key("dashboard", merchant_id)
        return await cls.delete(key)
    
    # === Provider Sync Caching ===
    
    @classmethod
    async def get_sync_status_cached(
        cls,
        merchant_id: str,
        provider_account_id: str,
        compute_fn,
    ) -> Dict[str, Any]:
        """Get provider sync status (cached for 15 minutes).
        
        Args:
            merchant_id: Merchant ID
            provider_account_id: Provider account ID
            compute_fn: Async function to compute sync status if not cached
        
        Returns:
            Sync status dict
        """
        key = cls._make_key("sync_status", merchant_id, provider_account_id)
        return await cls.get_or_compute(key, compute_fn, cls.PROVIDER_SYNC_TTL)
    
    @classmethod
    async def invalidate_sync_status(cls, merchant_id: str, provider_account_id: str = None) -> int:
        """Invalidate sync status cache."""
        if provider_account_id:
            key = cls._make_key("sync_status", merchant_id, provider_account_id)
            return 1 if await cls.delete(key) else 0
        else:
            pattern = cls._make_key("sync_status", merchant_id, "*")
            return await cls.delete_pattern(pattern)
    
    # === Reconciliation Caching ===
    
    @classmethod
    async def get_reconciliation_cached(
        cls,
        merchant_id: str,
        compute_fn,
    ) -> Dict[str, Any]:
        """Get reconciliation status (cached for 10 minutes).
        
        Args:
            merchant_id: Merchant ID
            compute_fn: Async function to compute reconciliation if not cached
        
        Returns:
            Reconciliation data dict
        """
        key = cls._make_key("reconciliation", merchant_id)
        return await cls.get_or_compute(key, compute_fn, cls.RECONCILIATION_TTL)
    
    @classmethod
    async def invalidate_reconciliation(cls, merchant_id: str) -> bool:
        """Invalidate reconciliation cache for a merchant."""
        key = cls._make_key("reconciliation", merchant_id)
        return await cls.delete(key)
    
    # === Query Result Caching ===
    
    @classmethod
    async def cache_query_result(
        cls,
        merchant_id: str,
        query_type: str,
        query_hash: str,
        result: Any,
        ttl: int = 300,
    ) -> bool:
        """Cache an arbitrary query result.
        
        Args:
            merchant_id: Merchant ID
            query_type: Type of query (e.g., 'incidents', 'transactions')
            query_hash: Hash of query parameters
            result: Query result to cache
            ttl: Time to live in seconds
        
        Returns:
            True if cached successfully
        """
        key = cls._make_key("query", merchant_id, query_type, query_hash)
        return await cls.set(key, result, ttl)
    
    @classmethod
    async def get_cached_query_result(
        cls,
        merchant_id: str,
        query_type: str,
        query_hash: str,
    ) -> Optional[Any]:
        """Get cached query result.
        
        Args:
            merchant_id: Merchant ID
            query_type: Type of query
            query_hash: Hash of query parameters
        
        Returns:
            Cached result or None if not found/expired
        """
        key = cls._make_key("query", merchant_id, query_type, query_hash)
        return await cls.get(key)
    
    @classmethod
    def compute_query_hash(cls, **params) -> str:
        """Compute hash of query parameters for caching."""
        sorted_params = sorted((k, str(v)) for k, v in params.items())
        param_str = "|".join(f"{k}={v}" for k, v in sorted_params)
        return hashlib.sha256(param_str.encode()).hexdigest()[:16]
    
    # === Stats/Monitoring ===
    
    @classmethod
    async def get_stats(cls) -> Dict[str, Any]:
        """Get cache statistics (from Redis INFO)."""
        try:
            client = await cls.get_client()
            if not client:
                return {"status": "unavailable"}
            info = await client.info()
            return {
                "status": "available",
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec", 0),
            }
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {"status": "error", "error": str(e)}
