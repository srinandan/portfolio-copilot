"""Unit tests for fundamentals caching (offline)."""

from orchestrator.data.fundamentals_cache import (
    CachedFundamentalsProvider,
    FirestoreFundamentalsCache,
    InMemoryTTLCache,
)
from orchestrator.executors.fundamentals import MockFundamentalsProvider


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _snapshot(ticker="AAPL"):
    return MockFundamentalsProvider().get_fundamentals(ticker)


# --- InMemoryTTLCache ------------------------------------------------------- #


def test_in_memory_cache_get_set_case_insensitive():
    cache = InMemoryTTLCache(ttl_seconds=100, clock=Clock())
    snap = _snapshot()
    cache.set("AAPL", snap)
    assert cache.get("aapl") is snap


def test_in_memory_cache_expires_after_ttl():
    clock = Clock(t=1000.0)
    cache = InMemoryTTLCache(ttl_seconds=100, clock=clock)
    cache.set("AAPL", _snapshot())
    assert cache.get("AAPL") is not None
    clock.t += 101  # advance past TTL
    assert cache.get("AAPL") is None


def test_in_memory_cache_miss_returns_none():
    assert InMemoryTTLCache().get("NONE") is None


# --- CachedFundamentalsProvider --------------------------------------------- #


class CountingProvider:
    def __init__(self, snap):
        self.snap = snap
        self.calls = 0

    def get_fundamentals(self, ticker):
        self.calls += 1
        return self.snap


def test_cached_provider_serves_from_cache_after_first_call():
    snap = _snapshot()
    underlying = CountingProvider(snap)
    cached = CachedFundamentalsProvider(underlying, InMemoryTTLCache(ttl_seconds=1000, clock=Clock()))

    first = cached.get_fundamentals("AAPL")
    second = cached.get_fundamentals("aapl")

    assert first is snap and second is snap
    assert underlying.calls == 1  # second call served from cache


# --- FirestoreFundamentalsCache (fake db) ----------------------------------- #


class FakeDoc:
    def __init__(self, data):
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return self._data


class FakeDocRef:
    def __init__(self, store, key):
        self._store = store
        self._key = key

    def get(self):
        return FakeDoc(self._store.get(self._key))

    def set(self, data):
        self._store[self._key] = data


class FakeCollection:
    def __init__(self, store):
        self._store = store

    def document(self, key):
        return FakeDocRef(self._store, key)


class FakeDB:
    def __init__(self):
        self._cols = {}

    def collection(self, name):
        return FakeCollection(self._cols.setdefault(name, {}))


def test_firestore_cache_roundtrip():
    cache = FirestoreFundamentalsCache(db=FakeDB(), ttl_seconds=100, clock=Clock())
    snap = _snapshot("MSFT")
    cache.set("MSFT", snap)
    got = cache.get("msft")
    assert got is not None
    assert got.model_dump(mode="json") == snap.model_dump(mode="json")


def test_firestore_cache_miss_returns_none():
    assert FirestoreFundamentalsCache(db=FakeDB()).get("AAPL") is None


def test_firestore_cache_expires():
    clock = Clock(t=1000.0)
    cache = FirestoreFundamentalsCache(db=FakeDB(), ttl_seconds=100, clock=clock)
    cache.set("AAPL", _snapshot())
    assert cache.get("AAPL") is not None
    clock.t += 101
    assert cache.get("AAPL") is None
