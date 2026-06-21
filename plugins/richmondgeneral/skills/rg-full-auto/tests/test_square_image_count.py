"""Unit tests for BatchOrchestrator._default_square_image_count — the live
Square catalog image-count lookup that backs the listing-image gate.

These tests MOCK the Square SDK and the token resolver so no real network call
is ever made. They cover:
  - item with object_id whose Square item_data has N image_ids -> returns N
  - item whose Square item has no images -> returns 0
  - missing object_id in label.json -> returns None (no lookup attempted)
  - missing token -> returns None (degrade to label.json fallback)
  - Square SDK unavailable (ImportError) -> returns None (un-synced machine)
  - Square error / raised exception -> returns None (graceful)
  - errors array on the response -> returns None
  - object not found (empty objects) -> returns None

They also exercise the end-to-end gate via the default (un-injected) path to
prove the real lookup feeds has_square_image: with a mocked Square returning
0 images the publish phases BLOCK; with >=1 they run.
"""
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import item_state as ist  # noqa: E402
import process_batch as pb  # noqa: E402


def _write_label(item_dir, payload):
    (item_dir / "label.json").write_text(json.dumps(payload))


class _FakeItemData:
    def __init__(self, image_ids):
        self.image_ids = image_ids


class _FakeObject:
    def __init__(self, image_ids):
        self.item_data = _FakeItemData(image_ids)


class _FakeBatchGetResponse:
    def __init__(self, objects=None, errors=None):
        self.objects = objects
        self.errors = errors


class _FakeCatalog:
    def __init__(self, response=None, raises=None):
        self._response = response
        self._raises = raises
        self.calls = []

    def batch_get(self, object_ids=None):
        self.calls.append(object_ids)
        if self._raises is not None:
            raise self._raises
        return self._response


class _FakeSquareClient:
    """Stand-in for square.client.Square; captures token and serves a catalog."""

    last_token = None

    def __init__(self, token=None):
        type(self).last_token = token
        self.catalog = _FAKE_CATALOG


# Reassigned per-test so the lazily-imported `Square(token=...)` returns our fake.
_FAKE_CATALOG = None


def _install_fake_square(monkeypatch, *, image_ids=None, errors=None,
                         objects_override=None, raises=None, import_error=False):
    """Install a fake `square.client` module so the lazy import inside
    _default_square_image_count resolves to our test double (no network).

    Set import_error=True to simulate the SDK being absent (un-synced machine).
    """
    global _FAKE_CATALOG
    if import_error:
        # Make `from square.client import Square` raise ImportError.
        monkeypatch.setitem(sys.modules, "square", None)
        monkeypatch.setitem(sys.modules, "square.client", None)
        return None

    if objects_override is not None:
        objects = objects_override
    elif image_ids is None and errors is None and raises is None:
        objects = None
    else:
        objects = [_FakeObject(image_ids)] if image_ids is not None else None

    response = _FakeBatchGetResponse(objects=objects, errors=errors)
    catalog = _FakeCatalog(response=response, raises=raises)
    _FAKE_CATALOG = catalog

    fake_module = types.ModuleType("square.client")
    fake_module.Square = _FakeSquareClient
    square_pkg = types.ModuleType("square")
    square_pkg.client = fake_module
    monkeypatch.setitem(sys.modules, "square", square_pkg)
    monkeypatch.setitem(sys.modules, "square.client", fake_module)
    return catalog


def _patch_token(monkeypatch, token="fake-token"):
    import sku_authority
    monkeypatch.setattr(sku_authority, "_resolve_square_token", lambda: token)


# ── _default_square_image_count: mocked Square ──

def test_count_returns_number_of_image_ids(tmp_path, monkeypatch):
    item = tmp_path / "RG-4000"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "OID2IMG"}}})

    catalog = _install_fake_square(monkeypatch, image_ids=["IMG1", "IMG2"])
    _patch_token(monkeypatch)

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path),
                                queue_path=str(tmp_path / "q.json"))
    assert orch._default_square_image_count(str(item)) == 2
    assert catalog.calls == [["OID2IMG"]]               # queried by object_id
    assert _FakeSquareClient.last_token == "fake-token"  # token threaded through


def test_count_returns_zero_when_item_has_no_images(tmp_path, monkeypatch):
    item = tmp_path / "RG-4001"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "OID0IMG"}}})

    _install_fake_square(monkeypatch, image_ids=[])  # item_data.image_ids == []
    _patch_token(monkeypatch)

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path),
                                queue_path=str(tmp_path / "q.json"))
    assert orch._default_square_image_count(str(item)) == 0


def test_count_returns_zero_when_image_ids_field_absent(tmp_path, monkeypatch):
    """item_data present but image_ids is None -> treated as 0 images."""
    item = tmp_path / "RG-4002"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "OIDNOFIELD"}}})

    _install_fake_square(monkeypatch, objects_override=[_FakeObject(None)])
    _patch_token(monkeypatch)

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path),
                                queue_path=str(tmp_path / "q.json"))
    assert orch._default_square_image_count(str(item)) == 0


def test_count_none_when_object_id_missing(tmp_path, monkeypatch):
    """No object_id in label.json -> None, and Square is never consulted."""
    item = tmp_path / "RG-4003"
    item.mkdir()
    _write_label(item, {"channels": {"square": {}}})

    catalog = _install_fake_square(monkeypatch, image_ids=["IMG"])
    _patch_token(monkeypatch)

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path),
                                queue_path=str(tmp_path / "q.json"))
    assert orch._default_square_image_count(str(item)) is None
    assert catalog.calls == []  # short-circuited before any Square call


def test_count_none_when_token_missing(tmp_path, monkeypatch):
    item = tmp_path / "RG-4004"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "OID"}}})

    catalog = _install_fake_square(monkeypatch, image_ids=["IMG"])
    _patch_token(monkeypatch, token=None)  # no token resolved

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path),
                                queue_path=str(tmp_path / "q.json"))
    assert orch._default_square_image_count(str(item)) is None
    assert catalog.calls == []  # never reached the SDK call


def test_count_none_when_sdk_unavailable(tmp_path, monkeypatch):
    """Un-synced machine: `square` SDK not importable -> None (no crash)."""
    item = tmp_path / "RG-4005"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "OID"}}})

    _install_fake_square(monkeypatch, import_error=True)
    _patch_token(monkeypatch)

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path),
                                queue_path=str(tmp_path / "q.json"))
    assert orch._default_square_image_count(str(item)) is None


def test_count_none_when_square_raises(tmp_path, monkeypatch):
    item = tmp_path / "RG-4006"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "OIDBOOM"}}})

    _install_fake_square(monkeypatch, raises=RuntimeError("network down"))
    _patch_token(monkeypatch)

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path),
                                queue_path=str(tmp_path / "q.json"))
    assert orch._default_square_image_count(str(item)) is None


def test_count_none_when_response_has_errors(tmp_path, monkeypatch):
    item = tmp_path / "RG-4007"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "OIDERR"}}})

    _install_fake_square(monkeypatch, errors=[{"code": "NOT_FOUND"}])
    _patch_token(monkeypatch)

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path),
                                queue_path=str(tmp_path / "q.json"))
    assert orch._default_square_image_count(str(item)) is None


def test_count_none_when_object_not_found(tmp_path, monkeypatch):
    """batch_get returns no objects (id absent) -> None (can't determine)."""
    item = tmp_path / "RG-4008"
    item.mkdir()
    _write_label(item, {"channels": {"square": {"object_id": "OIDGONE"}}})

    _install_fake_square(monkeypatch, objects_override=[])
    _patch_token(monkeypatch)

    orch = pb.BatchOrchestrator(items_dir=str(tmp_path),
                                queue_path=str(tmp_path / "q.json"))
    assert orch._default_square_image_count(str(item)) is None


# ── end-to-end: the real (un-injected) lookup feeds the gate ──

def _make_state_ready_for_phase4(tmp_path, sku):
    state = ist.ItemState(sku=sku, items_dir=str(tmp_path))
    for ph in ("phase_0", "phase_1", "phase_2", "phase_3", "phase_5", "phase_6"):
        state.complete_phase(ph)
    state.save()
    return state


def test_default_path_blocks_publish_when_live_count_zero(tmp_path, monkeypatch):
    """No square_image_count injected: the DEFAULT live lookup (mocked Square,
    0 images) must drive has_square_image to BLOCK phase_4."""
    sku = "RG-4100"
    item_dir = tmp_path / sku
    item_dir.mkdir()
    _write_label(item_dir, {"hero_qa": {"status": "pass"},
                            "channels": {"square": {"object_id": "OIDZERO"}}})

    _install_fake_square(monkeypatch, image_ids=[])  # live Square: zero images
    _patch_token(monkeypatch)

    state = _make_state_ready_for_phase4(tmp_path, sku)
    ran = []
    orch = pb.BatchOrchestrator(
        items_dir=str(tmp_path),
        phase_runner=lambda st, ph, idir: ran.append(ph) or {"outputs": {}},
        queue_path=str(tmp_path / "queue.json"),
    )
    # NOTE: square_image_count is NOT injected — exercises the real default path.
    orch._advance_item(state)

    assert "phase_4" not in ran
    assert state.phases["phase_4"].status == ist.PhaseStatus.BLOCKED
    parked = [q for q in state.questions if q.get("phase") == "phase_4"]
    assert parked and "no image" in parked[-1]["question"]


def test_default_path_allows_publish_when_live_count_positive(tmp_path, monkeypatch):
    """Default live lookup (mocked Square, >=1 image) -> publish phases run."""
    sku = "RG-4101"
    item_dir = tmp_path / sku
    item_dir.mkdir()
    _write_label(item_dir, {"hero_qa": {"status": "pass"},
                            "channels": {"square": {"object_id": "OIDOK"}}})

    _install_fake_square(monkeypatch, image_ids=["IMG1"])  # live Square: 1 image
    _patch_token(monkeypatch)

    state = _make_state_ready_for_phase4(tmp_path, sku)
    ran = []
    orch = pb.BatchOrchestrator(
        items_dir=str(tmp_path),
        phase_runner=lambda st, ph, idir: ran.append(ph) or {"outputs": {}},
        queue_path=str(tmp_path / "queue.json"),
    )
    orch._advance_item(state)

    assert "phase_4" in ran and "phase_7" in ran
    assert state.phases["phase_4"].status == ist.PhaseStatus.COMPLETED


def test_default_path_failclosed_when_square_down_and_label_empty(tmp_path, monkeypatch):
    """Fail-closed: live lookup raises (Square down) AND label.json records no
    image_ids -> the gate must BLOCK, never a false 'has image' pass."""
    sku = "RG-4102"
    item_dir = tmp_path / sku
    item_dir.mkdir()
    _write_label(item_dir, {"hero_qa": {"status": "pass"},
                            "channels": {"square": {"object_id": "OIDDOWN"}}})

    _install_fake_square(monkeypatch, raises=RuntimeError("offline"))
    _patch_token(monkeypatch)

    state = _make_state_ready_for_phase4(tmp_path, sku)
    ran = []
    orch = pb.BatchOrchestrator(
        items_dir=str(tmp_path),
        phase_runner=lambda st, ph, idir: ran.append(ph) or {"outputs": {}},
        queue_path=str(tmp_path / "queue.json"),
    )
    orch._advance_item(state)

    assert "phase_4" not in ran
    assert state.phases["phase_4"].status == ist.PhaseStatus.BLOCKED


def test_default_path_failopen_to_label_when_square_down_but_label_has_ids(tmp_path, monkeypatch):
    """Square down (live count None) but label.json records image_ids -> the
    fallback lets the publish phases run."""
    sku = "RG-4103"
    item_dir = tmp_path / sku
    item_dir.mkdir()
    _write_label(item_dir, {"hero_qa": {"status": "pass"},
                            "channels": {"square": {
                                "object_id": "OIDLBL", "image_ids": ["IMGX"]}}})

    _install_fake_square(monkeypatch, raises=RuntimeError("offline"))
    _patch_token(monkeypatch)

    state = _make_state_ready_for_phase4(tmp_path, sku)
    ran = []
    orch = pb.BatchOrchestrator(
        items_dir=str(tmp_path),
        phase_runner=lambda st, ph, idir: ran.append(ph) or {"outputs": {}},
        queue_path=str(tmp_path / "queue.json"),
    )
    orch._advance_item(state)

    assert "phase_4" in ran
    assert state.phases["phase_4"].status == ist.PhaseStatus.COMPLETED
