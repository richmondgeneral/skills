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


class LaggyCreateFakeStore(FakeStore):
    """Models Square eventual-consistency: after create(), the freshly-made sentinel
    stays invisible to read() (returns n=None) for `lag` reads, then appears.
    Reproduces the cold-start / recreate-after-deletion propagation window."""
    def __init__(self, rg_max=0, lag=0):
        super().__init__(n=None, rg_max=rg_max)
        self._lag = lag
        self._pending_n = None

    def create(self, n: int) -> None:
        self.create_calls += 1
        self._pending_n = n            # created on Square, not yet visible to search

    def read(self) -> CounterState:
        if self.unavailable:
            raise SquareUnavailable("fake down")
        if self.n is None and self._pending_n is not None:
            if self._lag > 0:
                self._lag -= 1         # still propagating
            else:
                self.n = self._pending_n   # now consistent / visible
                self.version = 1
        return CounterState(n=self.n, version=self.version, rg_max=self.rg_max)


def test_allocate_self_heal_survives_consistency_lag_without_burning_cas_budget():
    # The just-created sentinel is invisible for several reads (Square eventual
    # consistency). The self-heal must absorb that lag on its OWN budget and never
    # consume the CAS-conflict retry budget -- otherwise a cold-start / recreate
    # raises SkuAllocationError having never attempted a single CAS.
    store = LaggyCreateFakeStore(rg_max=30, lag=5)
    # Zero contention here, so a CAS budget of 1 must suffice; the 5-read propagation
    # lag is the self-heal's problem, not max_retries'.
    assert allocate_sku(store, max_retries=1) == "RG-0031"
    assert store.create_calls >= 1
    assert store.cas_calls == 1        # exactly one CAS, taken once the sentinel appeared


def test_allocate_hard_fails_bounded_when_sentinel_never_becomes_visible():
    # If a created sentinel never propagates (permanent inconsistency / silent create
    # failure), the self-heal must hard-fail with a BOUNDED error -- never loop forever.
    store = LaggyCreateFakeStore(rg_max=30, lag=10_000)   # effectively never visible
    with pytest.raises(SkuAllocationError):
        allocate_sku(store, max_retries=2, heal_retries=4)
    assert store.cas_calls == 0        # never reached a CAS; bounded by heal_retries


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
    # Uniqueness is NECESSARY BUT NOT SUFFICIENT as a CAS-correctness check: the fake's
    # lock serializes the n read/write, so even a version-IGNORING (broken) cas_set
    # still yields N unique SKUs (confirmed by mutation test -- 40/40 broken runs passed
    # these two asserts). The load-bearing assertion is conflict_count: all N threads
    # start from ONE barrier-snapshotted version, so a correct version-CAS lets exactly
    # one win that version and forces the other N-1 to conflict on their first CAS
    # (empirically exactly N-1, 200/200 runs); a broken CAS yields 0. Do NOT weaken the
    # conflict_count bound back to "> 0" -- that is one deletion away from a vacuous test.
    assert len(set(results)) == N                  # necessary, not sufficient (see comment)
    assert store.conflict_count >= N - 1           # LOAD-BEARING: stale-version writes are rejected


def test_square_store_is_constructible_without_network():
    from sku_authority import SquareCounterStore
    store = SquareCounterStore(client=object())   # inject dummy; no calls made
    assert hasattr(store, "read") and hasattr(store, "cas_set") and hasattr(store, "create")


# --- M-1: version-conflict detection must match the exact code, not a "version" substring ---

class _Err:
    """Minimal stand-in for square.types.error.Error (has .code / .detail / .category)."""
    def __init__(self, code, detail="", category="INVALID_REQUEST_ERROR"):
        self.code = code
        self.detail = detail
        self.category = category


class _FakeApiError(Exception):
    """Mimics square.core.api_error.ApiError: the SDK RAISES it on any non-2xx, carrying a
    parsed .errors list. Its str() embeds the error detail text (as the real one does), so a
    naive `"version" in str(e)` match trips on ANY error that merely mentions 'version'."""
    def __init__(self, errors):
        self.errors = errors
        super().__init__("API Error 400: " + "; ".join(e.detail for e in errors))


class _FakeCachedObj:
    def model_dump(self, mode=None, exclude_none=None):
        return {"type": "ITEM", "id": "#x", "version": 1,
                "item_data": {"name": "RG-SKU-COUNTER:0050"}}


class _RaisingCatalog:
    def __init__(self, exc):
        self._exc = exc

    def batch_upsert(self, **kwargs):
        raise self._exc


class _FakeClient:
    def __init__(self, catalog):
        self.catalog = catalog


def _store_whose_upsert_raises(exc):
    from sku_authority import SquareCounterStore
    store = SquareCounterStore(client=_FakeClient(_RaisingCatalog(exc)))
    store._cached_obj = _FakeCachedObj()
    return store


def test_is_version_conflict_matches_real_version_mismatch_code():
    from sku_authority import _is_version_conflict
    assert _is_version_conflict(
        [_Err("VERSION_MISMATCH", "Object version does not match the latest version.")]) is True


def test_is_version_conflict_ignores_unrelated_error_that_mentions_version():
    # Free text contains "version" but the code is unrelated -> NOT a conflict, or it gets
    # retried to exhaustion (SkuAllocationError) instead of surfacing the real cause.
    from sku_authority import _is_version_conflict
    unrelated = [{"category": "INVALID_REQUEST_ERROR", "code": "BAD_REQUEST",
                  "detail": "The provided API version is not supported."}]
    assert _is_version_conflict(unrelated) is False


def test_cas_set_retries_on_real_version_mismatch_apierror():
    # Square raises ApiError(VERSION_MISMATCH) on a stale-version upsert -> retry signal (False).
    store = _store_whose_upsert_raises(_FakeApiError([_Err("VERSION_MISMATCH", "stale version")]))
    assert store.cas_set(1, 50) is False


def test_cas_set_hard_fails_on_unrelated_apierror_mentioning_version():
    # An unrelated ApiError whose text contains "version" must PROPAGATE, not be retried.
    from sku_authority import SquareUnavailable
    store = _store_whose_upsert_raises(
        _FakeApiError([_Err("BAD_REQUEST", "The provided API version is not supported.")]))
    with pytest.raises(SquareUnavailable):
        store.cas_set(1, 50)


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
