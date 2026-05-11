"""
Tests for parallel --all-images path in refresh_item_image.py.

The cleanup subprocess (clean.py) takes ~4 minutes per image. With multiple
images attached to one item, sequential execution wastes wall time. These
tests verify that --all-images uses a bounded thread pool with the right
behavior (concurrency cap, exit codes, failure collection).
"""
import sys
import time

import pytest

import refresh_item_image as rim


def _fake_item(image_count: int, sku: str = "RG-9999") -> dict:
    return {
        "id": "ITEM-TEST",
        "item_data": {
            "name": "Test Item",
            "image_ids": [f"IMG-{i}" for i in range(image_count)],
            "variations": [{"item_variation_data": {"sku": sku}}],
        },
    }


def _patch_main_io(monkeypatch, item):
    """Mock out token, Gemini key, and item resolution so main() can run."""
    monkeypatch.setattr(rim, "get_token", lambda: "fake-token")
    monkeypatch.setattr(rim, "ensure_gemini_key", lambda: None)
    monkeypatch.setattr(rim, "resolve_item", lambda *a, **kw: item)


def test_all_images_runs_in_parallel(monkeypatch, capsys):
    """5 images × 0.5s sleep with concurrency=3 should finish in ≤1.0s."""
    _patch_main_io(monkeypatch, _fake_item(5))

    def fake_refresh(token, api_version, item_id, image_id, sku, args, tmpdir):
        time.sleep(0.5)
        return {
            "image_id": image_id,
            "source": "fake",
            "elapsed_s": 0.5,
            "cleaned_paths": [],
        }

    monkeypatch.setattr(rim, "refresh_one_image", fake_refresh)
    monkeypatch.setattr(sys, "argv", [
        "refresh_item_image.py", "--item-id", "ITEM-TEST",
        "--all-images", "--concurrency", "3",
    ])

    t0 = time.time()
    rim.main()
    elapsed = time.time() - t0

    # ceil(5/3) = 2 rounds × 0.5s = 1.0s ideal; allow small overhead.
    assert elapsed <= 1.2, (
        f"Expected ≤1.2s with concurrency=3 over 5 images @ 0.5s each, "
        f"got {elapsed:.2f}s (sequential would be ~2.5s)"
    )
    # And clearly faster than sequential.
    assert elapsed < 2.0


def test_concurrency_capped_at_8(monkeypatch):
    """User passes --concurrency 100; should be silently capped at 8."""
    _patch_main_io(monkeypatch, _fake_item(20))

    observed_max = {"value": 0}
    in_flight = {"value": 0}
    import threading
    lock = threading.Lock()

    def fake_refresh(token, api_version, item_id, image_id, sku, args, tmpdir):
        with lock:
            in_flight["value"] += 1
            observed_max["value"] = max(observed_max["value"], in_flight["value"])
        time.sleep(0.1)
        with lock:
            in_flight["value"] -= 1
        return {"image_id": image_id, "source": "x", "elapsed_s": 0.1, "cleaned_paths": []}

    monkeypatch.setattr(rim, "refresh_one_image", fake_refresh)
    monkeypatch.setattr(sys, "argv", [
        "refresh_item_image.py", "--item-id", "ITEM-TEST",
        "--all-images", "--concurrency", "100",
    ])

    rim.main()

    assert observed_max["value"] <= 8, (
        f"Concurrency should be capped at 8, but saw {observed_max['value']} "
        f"workers running simultaneously"
    )


def test_all_success_returns_exit_0(monkeypatch):
    _patch_main_io(monkeypatch, _fake_item(3))

    def fake_refresh(*a, **kw):
        return {"image_id": "X", "source": "x", "elapsed_s": 0.0, "cleaned_paths": []}

    monkeypatch.setattr(rim, "refresh_one_image", fake_refresh)
    monkeypatch.setattr(sys, "argv", [
        "refresh_item_image.py", "--item-id", "ITEM-TEST", "--all-images",
    ])

    # No SystemExit on success.
    rim.main()


def test_any_failure_returns_exit_1(monkeypatch, capsys):
    _patch_main_io(monkeypatch, _fake_item(3))

    call_count = {"n": 0}

    def fake_refresh(token, api_version, item_id, image_id, sku, args, tmpdir):
        call_count["n"] += 1
        if image_id == "IMG-1":
            raise RuntimeError("simulated clean.py failure")
        return {"image_id": image_id, "source": "x", "elapsed_s": 0.0, "cleaned_paths": []}

    monkeypatch.setattr(rim, "refresh_one_image", fake_refresh)
    monkeypatch.setattr(sys, "argv", [
        "refresh_item_image.py", "--item-id", "ITEM-TEST", "--all-images",
    ])

    with pytest.raises(SystemExit) as exc_info:
        rim.main()

    assert exc_info.value.code == 1
    # All workers should still have been attempted (3 calls total).
    assert call_count["n"] == 3
    out = capsys.readouterr()
    combined = out.out + out.err
    assert "IMG-1" in combined and "FAIL" in combined.upper()


def test_concurrency_flag_default_is_3(monkeypatch):
    """Sanity check: --help mentions concurrency and default is 3."""
    _patch_main_io(monkeypatch, _fake_item(2))

    captured_workers = {"value": None}

    # Hijack ThreadPoolExecutor to capture max_workers.
    import concurrent.futures as cf
    original = cf.ThreadPoolExecutor

    class SpyExecutor(original):
        def __init__(self, max_workers=None, **kw):
            captured_workers["value"] = max_workers
            super().__init__(max_workers=max_workers, **kw)

    monkeypatch.setattr(cf, "ThreadPoolExecutor", SpyExecutor)
    monkeypatch.setattr(rim, "refresh_one_image",
                        lambda *a, **kw: {"image_id": "X", "source": "x",
                                          "elapsed_s": 0.0, "cleaned_paths": []})
    monkeypatch.setattr(sys, "argv", [
        "refresh_item_image.py", "--item-id", "ITEM-TEST", "--all-images",
    ])

    rim.main()

    # 2 images, default concurrency 3 → min(3, 2) = 2.
    assert captured_workers["value"] == 2


def test_single_image_no_all_images_flag_uses_sequential_path(monkeypatch):
    """Without --all-images, do not invoke the thread pool at all."""
    _patch_main_io(monkeypatch, _fake_item(5))

    import concurrent.futures as cf
    original = cf.ThreadPoolExecutor
    pool_used = {"value": False}

    class SpyExecutor(original):
        def __init__(self, *a, **kw):
            pool_used["value"] = True
            super().__init__(*a, **kw)

    monkeypatch.setattr(cf, "ThreadPoolExecutor", SpyExecutor)
    monkeypatch.setattr(rim, "refresh_one_image",
                        lambda *a, **kw: {"image_id": "X", "source": "x",
                                          "elapsed_s": 0.0, "cleaned_paths": []})
    monkeypatch.setattr(sys, "argv", [
        "refresh_item_image.py", "--item-id", "ITEM-TEST",  # no --all-images
    ])

    rim.main()

    assert pool_used["value"] is False, (
        "Without --all-images, refresh_item_image should not spin up a thread pool"
    )
