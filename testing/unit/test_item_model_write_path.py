import json

from item_model.write_path import plan_channel_pushes
from item_model.models import PageRecord, Channel


def _page(listed):
    return PageRecord(sku="RG-0009", reference_price=95.0, listed_on=listed)


# ── Pure planner: plan_channel_pushes ────────────────────────────────────

def test_square_listed_with_variation_id_is_api_push():
    page = _page([Channel.SQUARE])
    registry = {"square": {"status": "listed", "variation_id": "WJ7"}}
    pushes = plan_channel_pushes(page, registry, 95.0)
    assert pushes == [{"channel": "square", "mode": "api", "variation_id": "WJ7", "amount_cents": 9500}]


def test_square_listed_without_variation_id_is_manual():
    page = _page([Channel.SQUARE])
    pushes = plan_channel_pushes(page, {"square": {"status": "listed"}}, 95.0)
    assert pushes == [{"channel": "square", "mode": "manual", "reason": "no variation_id in registry"}]


def test_other_channels_are_manual():
    page = _page([Channel.WHATNOT, Channel.MARKETPLACE])
    pushes = plan_channel_pushes(page, {}, 7.0)
    assert {p["channel"] for p in pushes} == {"whatnot", "marketplace"}
    assert all(p["mode"] == "manual" for p in pushes)


def test_not_listed_channel_absent():
    page = _page([Channel.SQUARE])
    pushes = plan_channel_pushes(page, {"square": {"status": "listed", "variation_id": "V"}}, 10.0)
    assert [p["channel"] for p in pushes] == ["square"]   # only listed channels


def test_cents_rounding():
    page = _page([Channel.SQUARE])
    pushes = plan_channel_pushes(page, {"square": {"status": "listed", "variation_id": "V"}}, 12.5)
    assert pushes[0]["amount_cents"] == 1250


# ── CLI page-side: apply_set_price dry-run (NO --apply, NO Square) ────────

def test_apply_set_price_dry_run_updates_page_and_plans_square_push(tmp_path):
    """Dry-run path: page reference price is written to disk, the square api push is
    planned, applied is False, and NO Square import/network happens."""
    from set_price import apply_set_price

    item_dir = tmp_path / "RG-0009"
    item_dir.mkdir(parents=True)
    label = {
        "sku": "RG-0009",
        "price": "95.00",
        "product_name": "A Thing",        # extra field must survive the merge-write
        "channels": {
            "square": {"status": "listed", "variation_id": "WJ7", "object_id": "BI2"},
            "whatnot": {"status": "listed"},
        },
    }
    (item_dir / "label.json").write_text(json.dumps(label), encoding="utf-8")

    result = apply_set_price(item_dir, 80.0)   # apply defaults to False

    # page reference price updated on disk
    written = json.loads((item_dir / "label.json").read_text(encoding="utf-8"))
    assert written["price"] == "80.00"
    assert written["product_name"] == "A Thing"     # extras preserved

    # plan includes the square api push (variation_id from registry) + whatnot manual
    assert result["sku"] == "RG-0009"
    assert result["page_updated"] is True
    assert result["applied"] is False
    square = [p for p in result["pushes"] if p["channel"] == "square"]
    assert square == [{"channel": "square", "mode": "api", "variation_id": "WJ7", "amount_cents": 8000}]
    assert any(p["channel"] == "whatnot" and p["mode"] == "manual" for p in result["pushes"])


def test_apply_set_price_dry_run_never_calls_resolve_square_token(tmp_path, monkeypatch):
    """SAFETY INVARIANT: the dry-run (apply=False) path must touch NO Keychain/.env/network.
    resolve_square_token() is the seam's only Keychain/.env reader, so we monkeypatch it to
    raise — if the dry-run path reached it, apply_set_price would blow up. It must not, even
    when the plan contains an actionable Square api push (variation_id present)."""
    import item_model.instance as inst
    from set_price import apply_set_price

    def _boom():  # pragma: no cover - must never be invoked on the dry-run path
        raise AssertionError("resolve_square_token() called on dry-run path — Keychain/.env touched")

    monkeypatch.setattr(inst, "resolve_square_token", _boom)

    item_dir = tmp_path / "RG-0009"
    item_dir.mkdir(parents=True)
    label = {
        "sku": "RG-0009",
        "price": "95.00",
        "channels": {"square": {"status": "listed", "variation_id": "WJ7"}},
    }
    (item_dir / "label.json").write_text(json.dumps(label), encoding="utf-8")

    result = apply_set_price(item_dir, 80.0)  # apply defaults to False — resolver must not fire

    assert result["applied"] is False
    assert json.loads((item_dir / "label.json").read_text(encoding="utf-8"))["price"] == "80.00"
    assert [p for p in result["pushes"] if p["channel"] == "square"][0]["mode"] == "api"
