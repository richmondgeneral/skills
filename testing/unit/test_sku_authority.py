import threading
import pytest
from sku_authority import (
    format_sku, format_counter_name, parse_counter_n, parse_rg_n,
    SkuAllocationError,
)
from sku_authority import allocate_sku, bootstrap, peek, CounterState, SquareUnavailable

def test_format_sku_zero_pads():
    assert format_sku(31) == "RG-0031"
    assert format_sku(7) == "RG-0007"

def test_format_counter_name_roundtrips():
    assert parse_counter_n(format_counter_name(30)) == 30

def test_parse_rg_n_matches_only_real_skus():
    assert parse_rg_n("RG-0030") == 30
    assert parse_rg_n("__RG_SKU_COUNTER__") is None      # sentinel never counts
    assert parse_rg_n("RG-SKU-COUNTER:0030") is None     # counter name never counts
    assert parse_rg_n("RG-0030-test") is None

def test_parse_counter_n_rejects_garbage():
    with pytest.raises(SkuAllocationError):
        parse_counter_n("not-a-counter")


class FakeStore:
    """In-memory CounterStore with version-CAS semantics, for tests."""
    def __init__(self, n=None, rg_max=0, unavailable=False, always_conflict=False):
        self.n = n
        self.version = 1 if n is not None else None
        self.rg_max = rg_max
        self.unavailable = unavailable
        self.always_conflict = always_conflict
        self.conflict_once = False
        self.create_calls = 0
        self.cas_calls = 0

    def read(self) -> CounterState:
        if self.unavailable:
            raise SquareUnavailable("fake down")
        return CounterState(n=self.n, version=self.version, rg_max=self.rg_max)

    def create(self, n: int) -> None:
        self.create_calls += 1
        self.n = n
        self.version = 1

    def cas_set(self, expected_version: int, n: int) -> bool:
        self.cas_calls += 1
        if self.always_conflict:
            self.version += 1
            return False
        if self.conflict_once:
            self.conflict_once = False
            self.version += 1          # simulate another writer's commit
            return False
        if expected_version != self.version:
            return False
        self.n = n
        self.version += 1
        return True


def test_allocate_clean_path_returns_next_and_increments():
    store = FakeStore(n=30, rg_max=30)
    assert allocate_sku(store) == "RG-0031"
    assert store.n == 31
    assert store.cas_calls == 1        # no double-increment


def test_allocate_retries_on_version_conflict():
    store = FakeStore(n=30, rg_max=30)
    store.conflict_once = True          # first CAS loses the race
    assert allocate_sku(store) == "RG-0031"
    assert store.cas_calls == 2         # retried exactly once


def test_allocate_reconciles_forward_when_square_is_ahead():
    store = FakeStore(n=30, rg_max=50)  # live catalog already has RG-0050
    assert allocate_sku(store) == "RG-0051"
    assert store.n == 51


def test_allocate_never_goes_backward():
    store = FakeStore(n=99, rg_max=10)
    assert allocate_sku(store) == "RG-0100"


def test_allocate_self_heals_when_sentinel_missing():
    store = FakeStore(n=None, rg_max=30)
    assert allocate_sku(store) == "RG-0031"
    assert store.create_calls == 1


def test_bootstrap_initializes_to_max_of_square_and_fs():
    store = FakeStore(n=None, rg_max=30)
    assert bootstrap(store, fs_max=29) == 30
    assert store.n == 30


def test_bootstrap_is_idempotent_when_present():
    store = FakeStore(n=42, rg_max=42)
    assert bootstrap(store, fs_max=0) == 42
    assert store.create_calls == 0


def test_allocate_raises_when_retries_exhausted():
    from sku_authority import SkuAllocationError
    store = FakeStore(n=30, rg_max=30, always_conflict=True)
    with pytest.raises(SkuAllocationError):
        allocate_sku(store, max_retries=3)
    assert store.cas_calls == 3


def test_allocate_hard_fails_when_square_unavailable():
    store = FakeStore(unavailable=True)
    with pytest.raises(SquareUnavailable):     # NO silent local-glob fallback
        allocate_sku(store)


class ThreadSafeFakeStore(FakeStore):
    def __init__(self, n, rg_max):
        super().__init__(n=n, rg_max=rg_max)
        self._lock = threading.Lock()
    def cas_set(self, expected_version, n):
        with self._lock:                       # Square serializes the CAS
            if expected_version != self.version:
                return False
            self.n = n
            self.version += 1
            return True


def test_concurrent_allocations_are_unique():
    store = ThreadSafeFakeStore(n=0, rg_max=0)
    results, errors = [], []
    def worker():
        try:
            results.append(allocate_sku(store, max_retries=100))
        except Exception as e:                 # noqa: BLE001
            errors.append(e)
    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert not errors
    assert len(results) == 20
    assert len(set(results)) == 20             # zero collisions
