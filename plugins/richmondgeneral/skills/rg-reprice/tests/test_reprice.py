"""Tests for reprice.py — the rg-reprice price-change cascade (Phase D).

TDD: written BEFORE the module. **No live network and no real subprocess.**
Every test that would otherwise touch Square monkeypatches the transport seam
(``square_client.square_request``) and the payment-link / QR helpers
(``square_client.create_payment_link`` / ``delete_payment_link`` /
``gen_qr_png``), and replaces ``reprice.subprocess.run`` with a capturing stub —
so the suite NEVER hits Square, NEVER writes a QR byte, and NEVER spawns the
page/gallery builders.

reprice.py imports ``square_client`` cross-skill (it adds
``../../rg-square-list/scripts`` to ``sys.path``); we import the SAME module here
the same way and monkeypatch on it, and reprice.py is written to call through a
held module reference (``sc.square_request`` etc.) so the patches are seen.

Run under the plugin uv env:

    cd plugins/richmondgeneral && uv run --with "qrcode[pil]" pytest \
        skills/rg-reprice/tests/test_reprice.py -q
"""

import json
import os
import sys

import pytest

# Put rg-reprice/scripts on the path so we can import the module by name. The
# module itself adds rg-square-list/scripts for the cross-skill square_client.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import reprice as rp  # noqa: E402

# The same square_client object reprice resolved — monkeypatch HERE is seen there
# because reprice calls through its held module reference (rp.sc).
sc = rp.sc  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — a tmp item dir with a minimal label.json carrying channels.square.
# ---------------------------------------------------------------------------

def _write_label(item_dir, **overrides):
    """Write a minimal label.json into item_dir and return (path, dict)."""
    label = {
        "sku": "RG-0099",
        "product_name": "RG-0099 — Test Widget",
        "price": "45.00",
        "price_status": "final — $45 (2026-06-20)",
        "channels": {
            "square": {
                "status": "listed",
                "object_id": "OBJ123",
                "variation_id": "VAR123",
                "buy_link": "https://square.link/u/OLD",
                "payment_link_id": "LINKOLD",
                "order_id": "ORDEROLD",
                "price": "45.00",
            }
        },
    }
    label.update(overrides)
    path = item_dir / "label.json"
    path.write_text(json.dumps(label, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path, label


@pytest.fixture
def item_dir(tmp_path):
    """An items/ root containing a single RG-0099 item dir.

    Returns the ITEMS ROOT (tmp_path); the item lives at tmp_path/RG-0099. We
    point reprice at this root via its ``items_root`` arg so nothing touches the
    real workspace items/.
    """
    d = tmp_path / "RG-0099"
    d.mkdir()
    _write_label(d)
    return tmp_path


# ---------------------------------------------------------------------------
# Stub installers — record calls without touching the network / disk / shell.
# ---------------------------------------------------------------------------

def _patch_request(monkeypatch, handler):
    """Install a fake square_request that records every call (ordered).

    ``handler(method, path, body) -> (status, parsed)`` produces the response.
    Returns the shared ``calls`` list (one dict per call, in order).
    """
    calls = []

    def fake_request(method, path, token, version=sc.API_VERSION, body=None):
        calls.append({"method": method, "path": path, "body": body})
        return handler(method, path, body)

    monkeypatch.setattr(sc, "square_request", fake_request)
    return calls


def _patch_paylinks(monkeypatch):
    """Install fake create/delete payment-link helpers.

    Returns a shared ``events`` list capturing ('delete', link_id) and
    ('create', body) IN CALL ORDER, so a test can assert delete-before-create.
    """
    events = []

    def fake_delete(token, link_id):
        events.append(("delete", link_id))
        return 200

    def fake_create(token, body):
        events.append(("create", body))
        return {
            "id": "LINKNEW",
            "url": "https://square.link/u/NEW",
            "order_id": "ORDERNEW",
        }

    monkeypatch.setattr(sc, "delete_payment_link", fake_delete)
    monkeypatch.setattr(sc, "create_payment_link", fake_create)
    return events


def _patch_qr(monkeypatch):
    """Install a fake gen_qr_png; returns the list of (url, out_path) calls."""
    qr_calls = []

    def fake_qr(url, out_path):
        qr_calls.append({"url": url, "out_path": out_path})

    monkeypatch.setattr(sc, "gen_qr_png", fake_qr)
    return qr_calls


def _patch_subprocess(monkeypatch):
    """Replace reprice.subprocess.run with a capturing stub.

    Returns the list of argv lists captured, in order. Never spawns a process.
    """
    runs = []

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(argv, **kwargs):
        runs.append({"argv": list(argv), "kwargs": kwargs})
        return _Result()

    monkeypatch.setattr(rp.subprocess, "run", fake_run)
    return runs


def _patch_token(monkeypatch):
    monkeypatch.setattr(sc, "resolve_token", lambda: "T")


def _full_patch(monkeypatch, request_handler):
    """Install ALL seams and return their capture handles."""
    _patch_token(monkeypatch)
    calls = _patch_request(monkeypatch, request_handler)
    events = _patch_paylinks(monkeypatch)
    qr = _patch_qr(monkeypatch)
    runs = _patch_subprocess(monkeypatch)
    return calls, events, qr, runs


def _ok_catalog_get(version=7):
    """A GET-catalog-object handler returning an ITEM_VARIATION at ``version``."""
    def handler(method, path, body):
        if method == "GET" and "/v2/catalog/object/" in path:
            return 200, {
                "object": {
                    "type": "ITEM_VARIATION",
                    "id": "VAR123",
                    "version": version,
                    "item_variation_data": {
                        "item_id": "OBJ123",
                        "name": "Regular",
                        "sku": "RG-0099",
                        "pricing_type": "FIXED_PRICING",
                        "price_money": {"amount": 4500, "currency": "USD"},
                    },
                }
            }
        if method == "POST" and "/v2/catalog/batch-upsert" in path:
            return 200, {"objects": []}
        raise AssertionError(f"unexpected request: {method} {path}")
    return handler


# ---------------------------------------------------------------------------
# (a) Square variation price — sparse fetch-patch-upsert.
# ---------------------------------------------------------------------------

def test_sparse_price_update_uses_fetched_version(monkeypatch, item_dir):
    """The variation upsert carries the GET-returned version and new cents."""
    calls, _events, _qr, _runs = _full_patch(monkeypatch, _ok_catalog_get(version=7))

    rp.reprice("RG-0099", 65, date="2026-06-21", items_root=str(item_dir))

    get = next(c for c in calls if c["method"] == "GET")
    upsert = next(c for c in calls if c["method"] == "POST"
                  and "batch-upsert" in c["path"])
    assert "/v2/catalog/object/VAR123" in get["path"]

    # Find the variation object in the upsert body (regardless of batches shape).
    obj = _find_upsert_object(upsert["body"])
    assert obj is not None, f"no object in upsert body: {upsert['body']}"
    assert obj.get("version") == 7, "upsert must carry the GET-fetched version"
    pm = obj["item_variation_data"]["price_money"]
    assert pm["amount"] == 6500, "price_money.amount must be the new cents"
    assert pm["currency"] == "USD"
    # Safe fetch-patch-upsert: sku + pricing_type preserved from the fetch.
    assert obj["item_variation_data"]["sku"] == "RG-0099"
    assert obj["item_variation_data"]["pricing_type"] == "FIXED_PRICING"


def _find_upsert_object(body):
    """Pull the single catalog object out of a batch-upsert body."""
    if not isinstance(body, dict):
        return None
    if "object" in body:
        return body["object"]
    for batch in body.get("batches") or []:
        objs = batch.get("objects") or []
        if objs:
            return objs[0]
    objs = body.get("objects") or []
    return objs[0] if objs else None


# ---------------------------------------------------------------------------
# (b) Payment link — delete-then-create, in order.
# ---------------------------------------------------------------------------

def test_link_deleted_then_recreated(monkeypatch, item_dir):
    """The OLD link is deleted BEFORE the new one is created."""
    _calls, events, _qr, _runs = _full_patch(monkeypatch, _ok_catalog_get())

    rp.reprice("RG-0099", 65, date="2026-06-21", items_root=str(item_dir))

    kinds = [e[0] for e in events]
    assert kinds == ["delete", "create"], f"expected delete then create, got {kinds}"
    assert events[0][1] == "LINKOLD", "must delete the recorded old link id"
    # The new link is built at the NEW price for the SAME variation.
    create_body = events[1][1]
    line = create_body["order"]["line_items"][0]
    assert line["catalog_object_id"] == "VAR123"
    assert create_body["order"]["reference_id"] == "RG-0099"


def test_create_link_redirect_and_shipping(monkeypatch, tmp_path):
    """Redirect URL targets the item page; ask_shipping reflects pickup-only."""
    # Pickup-only item → ask_for_shipping_address must be False.
    d = tmp_path / "RG-0099"
    d.mkdir()
    _write_label(d, fulfillment="local_pickup_only")
    _calls, events, _qr, _runs = _full_patch(monkeypatch, _ok_catalog_get())

    rp.reprice("RG-0099", 65, date="2026-06-21", items_root=str(tmp_path))

    create_body = events[1][1]
    assert create_body["checkout_options"]["redirect_url"] == \
        "https://richmondgeneral.github.io/items/RG-0099/"
    assert create_body["checkout_options"]["ask_for_shipping_address"] is False


# ---------------------------------------------------------------------------
# (d) label.json — fully patched.
# ---------------------------------------------------------------------------

def test_label_patched(monkeypatch, item_dir):
    """price, price_status, channels.square.*, and a dated refinement_log entry."""
    _full_patch(monkeypatch, _ok_catalog_get())

    rp.reprice("RG-0099", 65, date="2026-06-21", items_root=str(item_dir))

    label = json.loads((item_dir / "RG-0099" / "label.json").read_text())
    assert label["price"] == "65.00"
    assert "65.00" in label["price_status"]
    assert "45.00" in label["price_status"]  # old price referenced
    assert "2026-06-21" in label["price_status"]

    sq = label["channels"]["square"]
    assert sq["price"] == "65.00"
    assert sq["buy_link"] == "https://square.link/u/NEW"
    assert sq["payment_link_id"] == "LINKNEW"
    assert sq["order_id"] == "ORDERNEW"

    log = label["estimates"]["refinement_log"]
    assert any(e.get("date") == "2026-06-21" and "Repriced" in e.get("note", "")
               for e in log), f"no dated Repriced entry in {log}"
    # The note records both prices.
    repriced = [e for e in log if "Repriced" in e.get("note", "")][-1]
    assert "45.00" in repriced["note"] and "65.00" in repriced["note"]


def test_label_creates_estimates_when_absent(monkeypatch, tmp_path):
    """If estimates/refinement_log are missing they are created."""
    d = tmp_path / "RG-0099"
    d.mkdir()
    _write_label(d)  # no estimates key
    _full_patch(monkeypatch, _ok_catalog_get())

    rp.reprice("RG-0099", 65, date="2026-06-21", items_root=str(tmp_path))

    label = json.loads((d / "label.json").read_text())
    assert "estimates" in label
    assert isinstance(label["estimates"]["refinement_log"], list)
    assert len(label["estimates"]["refinement_log"]) == 1


# ---------------------------------------------------------------------------
# (e/f) Cascade — page then gallery, AFTER the label write.
# ---------------------------------------------------------------------------

def test_cascade_invokes_page_and_gallery(monkeypatch, item_dir):
    """subprocess argv include build_item_page.py <sku> then build_gallery.py
    --update-card <sku>, in that order."""
    _calls, _events, _qr, runs = _full_patch(monkeypatch, _ok_catalog_get())

    rp.reprice("RG-0099", 65, date="2026-06-21", items_root=str(item_dir))

    argvs = [r["argv"] for r in runs]
    # Locate the two builder invocations.
    page_idx = next(i for i, a in enumerate(argvs)
                    if any("build_item_page.py" in tok for tok in a))
    gallery_idx = next(i for i, a in enumerate(argvs)
                       if any("build_gallery.py" in tok for tok in a))
    assert page_idx < gallery_idx, "page must build before gallery"

    page_argv = argvs[page_idx]
    gallery_argv = argvs[gallery_idx]
    assert "RG-0099" in page_argv
    assert "--update-card" in gallery_argv
    assert "RG-0099" in gallery_argv
    # cwd is the repo root (parent of items/), passed to subprocess.run. Assert it
    # actually contains items/scripts/build_item_page.py so a future fixed-
    # parents[N] regression (e.g. resolving to ~/.claude/plugins/cache, which has
    # no items/) is caught here, not in production.
    page_kwargs = runs[page_idx]["kwargs"]
    gallery_kwargs = runs[gallery_idx]["kwargs"]
    assert "cwd" in page_kwargs
    assert "cwd" in gallery_kwargs
    marker = os.path.join("items", "scripts", "build_item_page.py")
    assert os.path.exists(os.path.join(page_kwargs["cwd"], marker)), (
        f"page cwd {page_kwargs['cwd']!r} is not a workspace root "
        f"(missing {marker})"
    )
    assert os.path.exists(os.path.join(gallery_kwargs["cwd"], marker)), (
        f"gallery cwd {gallery_kwargs['cwd']!r} is not a workspace root "
        f"(missing {marker})"
    )


# ---------------------------------------------------------------------------
# (c) QR — rendered for the new buy link.
# ---------------------------------------------------------------------------

def test_qr_regenerated_for_new_link(monkeypatch, item_dir):
    """gen_qr_png is called with the NEW buy link and the item's qr-buy.png."""
    _calls, _events, qr, _runs = _full_patch(monkeypatch, _ok_catalog_get())

    rp.reprice("RG-0099", 65, date="2026-06-21", items_root=str(item_dir))

    assert len(qr) == 1
    assert qr[0]["url"] == "https://square.link/u/NEW"
    assert qr[0]["out_path"].endswith(os.path.join("RG-0099", "qr-buy.png"))


def test_qr_importerror_does_not_crash(monkeypatch, item_dir):
    """A missing qrcode dep (ImportError) warns but does not abort the cascade."""
    _patch_token(monkeypatch)
    _patch_request(monkeypatch, _ok_catalog_get())
    _patch_paylinks(monkeypatch)
    runs = _patch_subprocess(monkeypatch)

    def boom(url, out_path):
        raise ImportError("no qrcode")

    monkeypatch.setattr(sc, "gen_qr_png", boom)

    # Must not raise; label + cascade still complete.
    rp.reprice("RG-0099", 65, date="2026-06-21", items_root=str(item_dir))
    label = json.loads((item_dir / "RG-0099" / "label.json").read_text())
    assert label["price"] == "65.00"
    assert len(runs) >= 2  # page + gallery still ran


# ---------------------------------------------------------------------------
# Dry run — ZERO side effects.
# ---------------------------------------------------------------------------

def test_dry_run_no_side_effects(monkeypatch, item_dir):
    """dry_run makes ZERO square_request/create/delete/qr/subprocess calls AND
    leaves label.json byte-for-byte unchanged."""
    label_path = item_dir / "RG-0099" / "label.json"
    before = label_path.read_bytes()

    calls, events, qr, runs = _full_patch(monkeypatch, _ok_catalog_get())
    # Also guard the token resolver: dry-run must not even resolve a token.
    token_calls = []
    monkeypatch.setattr(sc, "resolve_token",
                        lambda: token_calls.append(1) or "T")

    plan = rp.reprice("RG-0099", 65, dry_run=True, date="2026-06-21",
                      items_root=str(item_dir))

    assert calls == [], "dry-run made a square_request call"
    assert events == [], "dry-run created/deleted a payment link"
    assert qr == [], "dry-run generated a QR"
    assert runs == [], "dry-run spawned a subprocess"
    assert token_calls == [], "dry-run resolved a token"
    assert label_path.read_bytes() == before, "dry-run mutated label.json"
    # The plan still reports what WOULD happen.
    assert plan.get("dry_run") is True
    assert plan.get("sku") == "RG-0099"
    assert plan.get("new_price") == "65.00"
    assert plan.get("old_price") == "45.00"


# ---------------------------------------------------------------------------
# _find_repo_root — cwd-anchored workspace resolution (the cache-safe fix).
# ---------------------------------------------------------------------------

def test_find_repo_root_from_cwd(tmp_path, monkeypatch):
    """With items/scripts/build_item_page.py under cwd, _find_repo_root returns
    that dir — proving it anchors to the RUN location (not this file's path, so
    the dual-copy cache still finds the real workspace)."""
    marker = tmp_path / "items" / "scripts" / "build_item_page.py"
    marker.parent.mkdir(parents=True)
    marker.write_text("# stub builder\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    found = rp._find_repo_root()

    # Compare resolved paths (macOS /var → /private/var symlink etc.).
    assert found.resolve() == tmp_path.resolve(), (
        f"_find_repo_root returned {found!r}, expected the cwd holding the marker"
    )


def test_find_repo_root_prefers_cwd_over_file_ancestors(tmp_path, monkeypatch):
    """cwd is searched BEFORE this file's ancestors: when the planted marker is
    nearer than the real workspace, _find_repo_root returns the cwd one. This is
    the cache-safety property — run location wins over __file__."""
    nested = tmp_path / "a" / "b"
    marker = nested / "items" / "scripts" / "build_item_page.py"
    marker.parent.mkdir(parents=True)
    marker.write_text("# stub builder\n", encoding="utf-8")

    monkeypatch.chdir(nested)
    found = rp._find_repo_root()

    assert found.resolve() == nested.resolve()
    # And it is NOT this test file's real-workspace root (the planted one wins).
    assert found.resolve() != os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))


def test_find_repo_root_raises_when_missing(tmp_path, monkeypatch):
    """From a cwd with no marker, AND when this file's ancestors also lack one,
    _find_repo_root raises the actionable RuntimeError. We make the __file__
    branch miss by pointing reprice.__file__ at the bare tmp dir (whose ancestors
    contain no items/scripts/build_item_page.py)."""
    # cwd: a tmp dir with no marker anywhere above it.
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    # Make the __file__ fallback also miss: ancestors of this path have no marker.
    monkeypatch.setattr(rp, "__file__", str(tmp_path / "nope" / "reprice.py"))

    with pytest.raises(RuntimeError, match="cannot locate the workspace root"):
        rp._find_repo_root()


def test_find_repo_root_does_not_run_at_import():
    """Importing the module must never raise (resolution is lazy). The module is
    already imported at top of this file; assert the function exists and REPO_ROOT
    is NOT computed eagerly at import time."""
    assert callable(rp._find_repo_root)
    # A fixed eager REPO_ROOT would reintroduce the cache bug.
    assert not hasattr(rp, "REPO_ROOT"), (
        "REPO_ROOT must not be a module-level constant — resolve lazily via "
        "_find_repo_root() so the dual-copy cache anchors to cwd, not __file__."
    )


# ---------------------------------------------------------------------------
# Loud builder-failure warning — a non-zero builder exit goes to stderr.
# ---------------------------------------------------------------------------

def test_builder_nonzero_exit_warns_loudly(monkeypatch, item_dir, capsys):
    """When build_item_page.py exits non-zero, reprice keeps going (check=False)
    but prints a loud STALE-price warning to STDERR and the plan still carries
    page_exit/gallery_exit."""
    _patch_token(monkeypatch)
    _patch_request(monkeypatch, _ok_catalog_get())
    _patch_paylinks(monkeypatch)
    _patch_qr(monkeypatch)

    class _Fail:
        returncode = 2
        stdout = ""
        stderr = ""

    def fake_run(argv, **kwargs):
        return _Fail()

    monkeypatch.setattr(rp.subprocess, "run", fake_run)

    plan = rp.reprice("RG-0099", 65, date="2026-06-21", items_root=str(item_dir))

    err = capsys.readouterr().err
    assert "rg-reprice" in err and "STALE" in err
    assert "build_item_page.py exited 2" in err
    assert "build_gallery.py exited 2" in err
    # The money path still completed and the exits are reported in the plan.
    assert plan["page_exit"] == 2
    assert plan["gallery_exit"] == 2
    label = json.loads((item_dir / "RG-0099" / "label.json").read_text())
    assert label["price"] == "65.00"


def test_main_returns_nonzero_on_builder_failure(monkeypatch, item_dir, capsys):
    """main() exits non-zero when a builder failed (so CI/automation notices a
    possibly-stale public page), after the loud per-step warnings."""
    _patch_token(monkeypatch)
    _patch_request(monkeypatch, _ok_catalog_get())
    _patch_paylinks(monkeypatch)
    _patch_qr(monkeypatch)

    class _Fail:
        returncode = 2
        stdout = ""
        stderr = ""

    monkeypatch.setattr(rp.subprocess, "run", lambda argv, **kw: _Fail())
    # Point the real-run items/ default at our tmp dir by patching argv parsing:
    # main() doesn't take items_root, so patch reprice() to inject it.
    real_reprice = rp.reprice
    monkeypatch.setattr(
        rp, "reprice",
        lambda sku, price, **kw: real_reprice(
            sku, price, items_root=str(item_dir),
            **{k: v for k, v in kw.items() if k != "items_root"}),
    )

    rc = rp.main(["RG-0099", "65", "--date", "2026-06-21"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "a page/gallery builder failed" in err
