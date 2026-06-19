from pricing_preflight import ensure_fresh_cache


class _FakeSync:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, 0

    def __call__(self):
        self.calls += 1
        return {"ok": self.ok, "synced": 3}


def test_runs_sync_and_reports():
    f = _FakeSync()
    res = ensure_fresh_cache(sync=f)
    assert f.calls == 1 and res["ok"] is True


def test_surfaces_sync_failure_without_raising():
    res = ensure_fresh_cache(sync=_FakeSync(ok=False))
    assert res["ok"] is False  # caller decides; never silently trust stale cache
