import threading
import pytest
from sku_authority import (
    format_sku, format_counter_name, parse_counter_n, parse_rg_n,
    allocate_sku, bootstrap, peek, CounterState,
    SkuAllocationError, SquareUnavailable,
)

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


def test_peek_returns_current_n_without_incrementing():
    store = FakeStore(n=42, rg_max=42)
    assert peek(store) == 42
    assert store.cas_calls == 0


def test_allocate_raises_when_retries_exhausted():
    store = FakeStore(n=30, rg_max=30, always_conflict=True)
    with pytest.raises(SkuAllocationError):
        allocate_sku(store, max_retries=3)
    assert store.cas_calls == 3


def test_allocate_hard_fails_when_square_unavailable():
    store = FakeStore(unavailable=True)
    with pytest.raises(SquareUnavailable):     # NO silent local-glob fallback
        allocate_sku(store)


class ContendingFakeStore(FakeStore):
    """Forces real version-CAS contention: a one-shot barrier makes every thread
    read the SAME version before any thread does its first CAS, so conflicts
    actually occur and allocate_sku's retry path is genuinely exercised.

    The version is snapshotted by the barrier's action (which runs once, in a
    single thread, the instant the last thread arrives) so every thread's first
    read returns that identical pre-CAS version -- otherwise the GIL would let
    each thread lazily read an already-advanced version and no conflict would
    ever occur (making the test vacuous, the very failure mode it guards)."""
    def __init__(self, n, rg_max, n_threads):
        super().__init__(n=n, rg_max=rg_max)
        self._lock = threading.Lock()
        self._barrier = threading.Barrier(n_threads, action=self._snapshot_version)
        self._first = threading.local()
        self._snapshot = None
        self.conflict_count = 0

    def _snapshot_version(self):
        self._snapshot = self.version     # frozen once, before any thread's first CAS

    def read(self) -> CounterState:
        if not getattr(self._first, "done", False):
            self._first.done = True
            self._barrier.wait()          # all threads start from the same version
            return CounterState(n=self.n, version=self._snapshot, rg_max=self.rg_max)
        return CounterState(n=self.n, version=self.version, rg_max=self.rg_max)

    def cas_set(self, expected_version, n):
        with self._lock:                  # Square serializes the CAS
            if expected_version != self.version:
                self.conflict_count += 1
                return False
            self.n = n
            self.version += 1
            return True


def test_concurrent_allocations_are_unique_under_contention():
    N = 20
    store = ContendingFakeStore(n=0, rg_max=0, n_threads=N)
    results, errors = [], []
    def worker():
        try:
            results.append(allocate_sku(store, max_retries=1000))
        except Exception as e:            # noqa: BLE001
            errors.append(e)
    threads = [threading.Thread(target=worker) for _ in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(results) == N
    assert len(set(results)) == N          # zero collisions
    assert store.conflict_count > 0        # PROVES real contention occurred (retry path exercised)


def test_square_store_is_constructible_without_network():
    from sku_authority import SquareCounterStore
    store = SquareCounterStore(client=object())   # inject dummy; no calls made
    assert hasattr(store, "read") and hasattr(store, "cas_set") and hasattr(store, "create")


def test_cli_help_runs():
    import subprocess
    import sys
    import sku_authority
    path = sku_authority.__file__
    r = subprocess.run([sys.executable, path, "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "bootstrap" in r.stdout and "peek" in r.stdout


def test_process_new_item_has_no_cwd_glob():
    import pathlib
    import process_new_item
    src = pathlib.Path(process_new_item.__file__).read_text()
    assert "glob('RG-*')" not in src and 'glob("RG-*")' not in src


def test_resolve_square_token_prefers_env(monkeypatch):
    from sku_authority import _resolve_square_token
    monkeypatch.setenv("SQUARE_ACCESS_TOKEN", "tok-abc")
    assert _resolve_square_token() == "tok-abc"


def test_sku_authority_has_no_item_model_dependency():
    # Token resolution must be self-contained: standalone / osascript-bridge runs
    # cannot import item_model (it is only on sys.path under tests via conftest).
    # This locks the regression the live integration check surfaced.
    import inspect
    import sku_authority
    assert "item_model" not in inspect.getsource(sku_authority)
