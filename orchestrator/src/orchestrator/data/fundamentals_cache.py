"""Caching for fundamentals data.

Fundamentals change at most quarterly, and the free data tiers are rate-limited
(and SEC EDGAR asks for polite request volume), so every FundamentalsProvider
should sit behind a TTL cache. This module provides:

- `FundamentalsCache` — the cache interface.
- `InMemoryTTLCache` — process-local default; zero dependencies, used in tests.
- `FirestoreFundamentalsCache` — shared, persistent cache across instances.
- `CachedFundamentalsProvider` — decorates any provider with a cache read/write.

Cached values are public financial data only (no user data), so a shared store
is fine.
"""

import time
from typing import Callable, Optional, Protocol, runtime_checkable

from ..contracts.fundamentals import FundamentalsSnapshot
from ..logger import get_logger

logger = get_logger(__name__)

DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h; fundamentals move at most quarterly.
DEFAULT_CACHE_COLLECTION = "fundamentals_cache"


@runtime_checkable
class FundamentalsCache(Protocol):
    """A ticker-keyed cache of FundamentalsSnapshot with TTL semantics."""

    def get(self, ticker: str) -> Optional[FundamentalsSnapshot]:  # pragma: no cover - interface
        ...

    def set(self, ticker: str, snapshot: FundamentalsSnapshot) -> None:  # pragma: no cover - interface
        ...


class InMemoryTTLCache:
    """Process-local TTL cache. Default cache; also used in tests.

    `clock` is injectable so tests can advance time deterministically.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS, clock: Callable[[], float] = time.time):
        self._ttl = ttl_seconds
        self._clock = clock
        self._store: dict[str, tuple[FundamentalsSnapshot, float]] = {}

    def get(self, ticker: str) -> Optional[FundamentalsSnapshot]:
        key = ticker.upper()
        entry = self._store.get(key)
        if entry is None:
            return None
        snapshot, stored_at = entry
        if self._clock() - stored_at > self._ttl:
            del self._store[key]
            return None
        return snapshot

    def set(self, ticker: str, snapshot: FundamentalsSnapshot) -> None:
        self._store[ticker.upper()] = (snapshot, self._clock())


class FirestoreFundamentalsCache:
    """Persistent fundamentals cache backed by Firestore.

    Documents live in `collection` keyed by uppercase ticker, storing the
    JSON-serialized snapshot plus a `cached_at` epoch used for TTL checks. `db`
    is injectable (a `google.cloud.firestore.Client`-like object) so it can be
    unit-tested against a fake; when omitted, a real client is created lazily.
    """

    def __init__(
        self,
        db: object = None,
        collection: str = DEFAULT_CACHE_COLLECTION,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ):
        self._db = db
        self._collection = collection
        self._ttl = ttl_seconds
        self._clock = clock

    def _database(self):
        if self._db is None:
            from google.cloud import firestore  # imported lazily to keep offline paths dependency-free

            self._db = firestore.Client()
        return self._db

    def get(self, ticker: str) -> Optional[FundamentalsSnapshot]:
        key = ticker.upper()
        try:
            doc = self._database().collection(self._collection).document(key).get()
            if not getattr(doc, "exists", False):
                return None
            data = doc.to_dict() or {}
            cached_at = data.get("cached_at")
            if cached_at is None or (self._clock() - float(cached_at)) > self._ttl:
                return None
            return FundamentalsSnapshot.model_validate(data["snapshot"])
        except Exception as e:  # never let a cache miss/parse error break the request
            logger.warning("FirestoreFundamentalsCache.get failed for %s: %s", key, e)
            return None

    def set(self, ticker: str, snapshot: FundamentalsSnapshot) -> None:
        key = ticker.upper()
        try:
            payload = {"cached_at": self._clock(), "snapshot": snapshot.model_dump(mode="json")}
            self._database().collection(self._collection).document(key).set(payload)
        except Exception as e:  # a cache write failure must not break the request
            logger.warning("FirestoreFundamentalsCache.set failed for %s: %s", key, e)


class CachedFundamentalsProvider:
    """Decorates a FundamentalsProvider with a read-through TTL cache."""

    def __init__(self, provider, cache: FundamentalsCache):
        self._provider = provider
        self._cache = cache

    def get_fundamentals(self, ticker: str) -> FundamentalsSnapshot:
        key = ticker.upper()
        cached = self._cache.get(key)
        if cached is not None:
            logger.debug("Fundamentals cache hit for %s", key)
            return cached
        snapshot = self._provider.get_fundamentals(key)
        self._cache.set(key, snapshot)
        return snapshot
