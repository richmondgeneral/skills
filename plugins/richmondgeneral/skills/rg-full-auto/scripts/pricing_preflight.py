#!/usr/bin/env python3

"""
Pricing preflight
=================

Make a Square cache sync a precondition for any pricing read. RG-0030 was
priced against a stale cache ($75 vs the real $45); this wrapper surfaces
staleness so an appraisal can warn-and-proceed or stop — it never silently
trusts the cache, and it never raises.
"""

from typing import Callable, Optional


def ensure_fresh_cache(sync: Optional[Callable[[], dict]] = None) -> dict:
    """Run a cache sync and report the result, normalized to an ``ok`` bool.

    The caller (the Phase 1 appraisal) decides whether to warn-and-proceed or
    stop on a stale/failed cache — this function only surfaces the outcome and
    never raises.

    :param sync: optional zero-arg syncer (used by tests). If omitted, the real
        Square cache-sync entrypoint is resolved lazily inside this function so
        unit tests need no network/MongoDB.
    :returns: a dict containing at least an ``"ok"`` bool. On any failure
        resolving or running the sync, ``{"ok": False, "reason": "<why>"}``.
    """
    if sync is not None:
        try:
            result = sync() or {}
        except Exception as exc:  # never raise — surface, don't crash
            return {"ok": False, "reason": f"sync raised: {exc}"}
        return {**result, "ok": bool(result.get("ok"))}

    # Production default: resolve the real cache sync lazily so the import never
    # touches unit tests. SquareCacheWrapper.sync_cache() shells out to
    # square_cache.sh and reports {"success": bool, ...}; normalize to "ok".
    try:
        from cache_wrapper import SquareCacheWrapper
    except Exception as exc:
        return {"ok": False, "reason": f"cannot import cache sync: {exc}"}

    try:
        result = SquareCacheWrapper().sync_cache() or {}
    except Exception as exc:
        return {"ok": False, "reason": f"cache sync failed: {exc}"}

    return {**result, "ok": bool(result.get("success"))}
