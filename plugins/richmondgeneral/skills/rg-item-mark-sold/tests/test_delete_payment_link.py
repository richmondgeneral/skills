"""Regression tests for delete_payment_link.py.

Headline bug (2026-06-20, RG-0014): discovery matched a payment link only when
the SKU appeared as a substring in the link's `description` or `payment_note`,
and `--id` merely *filtered within* those SKU matches — so `--id` could not
rescue a link the SKU filter had already excluded. RG-0014's live link had BOTH
`description` and `payment_note` = null, so the helper printed "No payment link
found" and would have silently left it live (phantom-charge risk).

These tests pin the fix: explicit selectors (--id / --url / --order-id) reach a
null-metadata link directly, bypassing the SKU match, and the read-only audit
mode flags a live link that maps to an already-sold item.

Stdlib-only script → stdlib-only test friendly; run under the repo venv:
    cd plugins/richmondgeneral && uv run pytest \
        skills/rg-item-mark-sold/tests/test_delete_payment_link.py -q
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import delete_payment_link as dpl  # noqa: E402


# --- The real RG-0014 link that the SKU filter excluded (both fields null) ----
RG0014_LINK = {
    "id": "2PE4WMYVYB6TXE2V",
    "url": "https://square.link/u/WYk1Yl12",
    "long_url": (
        "https://checkout.square.site/merchant/7MM9AFJAD0XHW/order/"
        "Td1qji0tORadRLBNfgZGWR0WIjFZY"
    ),
    "description": None,
    "payment_note": None,
    "order_id": "Td1qji0tORadRLBNfgZGWR0WIjFZY",
    "created_at": "2025-12-21T14:06:00Z",
}

# A normal, SKU-tagged decoy link for a *different*, still-available item.
RG0050_LINK = {
    "id": "6O42ERXZU4TBERKC",
    "url": "https://square.link/u/AbCdEf99",
    "long_url": "https://checkout.square.site/merchant/7MM9AFJAD0XHW/order/ORDER50",
    "description": "RG-0050 - Vintage Brass Lamp",
    "payment_note": "RG-0050",
    "order_id": "ORDER50",
    "created_at": "2026-06-01T00:00:00Z",
}

LINKS = [RG0014_LINK, RG0050_LINK]


# ---------------------------------------------------------------------------
# match_links — guard the existing word-boundary behavior (must not regress)
# ---------------------------------------------------------------------------

def test_match_links_word_boundary_does_not_overmatch():
    links = [{"description": "RG-0020 - other", "payment_note": None}]
    assert dpl.match_links(links, "RG-0002") == []   # RG-0002 must NOT hit RG-0020


def test_match_links_finds_sku_in_description_or_note():
    assert dpl.match_links(LINKS, "RG-0050") == [RG0050_LINK]


# ---------------------------------------------------------------------------
# select_links — the fix. Explicit selectors reach the null-metadata link.
# ---------------------------------------------------------------------------

def test_sku_alone_cannot_find_null_metadata_link():
    # Reproduces the bug's precondition: nothing in description/payment_note,
    # so a SKU-only search can never surface RG-0014's link.
    assert dpl.select_links(LINKS, sku="RG-0014") == []


def test_id_finds_null_metadata_link_bypassing_sku():
    # REGRESSION: old code filtered --id *within* SKU matches (empty) -> missed.
    got = dpl.select_links(LINKS, sku="RG-0014", link_id="2PE4WMYVYB6TXE2V")
    assert got == [RG0014_LINK]


def test_id_ignores_a_wrong_sku_entirely():
    # --id must win even when a (mismatched) SKU is also supplied.
    got = dpl.select_links(LINKS, sku="RG-9999", link_id="2PE4WMYVYB6TXE2V")
    assert got == [RG0014_LINK]


def test_url_slug_finds_null_metadata_link():
    assert dpl.select_links(LINKS, url="WYk1Yl12") == [RG0014_LINK]


def test_full_short_url_finds_null_metadata_link():
    assert dpl.select_links(LINKS, url="https://square.link/u/WYk1Yl12") == [RG0014_LINK]


def test_order_id_finds_null_metadata_link():
    got = dpl.select_links(LINKS, order_id="Td1qji0tORadRLBNfgZGWR0WIjFZY")
    assert got == [RG0014_LINK]


def test_sku_path_unaffected_for_tagged_links():
    assert dpl.select_links(LINKS, sku="RG-0050") == [RG0050_LINK]


def test_no_selector_returns_empty():
    assert dpl.select_links(LINKS) == []


# ---------------------------------------------------------------------------
# audit_links — read-only sweep flags sold items that still have a live link
# ---------------------------------------------------------------------------

def _sev_by_sku(findings):
    return {f["sku"]: f["severity"] for f in findings}


def test_audit_flags_sold_item_with_live_null_metadata_link():
    # RG-0014 is sold and its status.json notes still mention the short slug,
    # so the link is attributable by record-scan even though metadata is null.
    items = [
        {"sku": "RG-0014", "status": "sold",
         "blob": "square payment link square.link/u/wyk1yl12 deactivated"},
        {"sku": "RG-0050", "status": "available", "blob": "rg-0050 active listing"},
    ]
    findings = dpl.audit_links(LINKS, items)
    sev = _sev_by_sku(findings)
    assert sev["RG-0014"] == "CRITICAL"     # sold item, live link -> phantom risk
    assert sev["RG-0050"] == "OK"           # available item, live link -> expected
    assert dpl.audit_has_critical(findings) is True


def test_audit_attributes_sold_link_by_sku_metadata():
    # A sold item whose link still carries the SKU in its description.
    items = [{"sku": "RG-0050", "status": "sold", "blob": "rg-0050 sold"}]
    findings = dpl.audit_links([RG0050_LINK], items)
    assert findings[0]["severity"] == "CRITICAL"
    assert findings[0]["attributed_by"] == "metadata"


def test_audit_warns_on_unattributable_live_link():
    # Null metadata, no item record references the slug/order/id -> manual review.
    items = [{"sku": "RG-0050", "status": "available", "blob": "nothing relevant"}]
    findings = dpl.audit_links([RG0014_LINK], items)
    assert findings[0]["severity"] == "WARN"
    assert findings[0]["sku"] is None
    assert dpl.audit_has_critical(findings) is False


# ---------------------------------------------------------------------------
# load_item_records — the filesystem glue audit_links sits on top of
# ---------------------------------------------------------------------------

def test_load_item_records_reads_status_and_blob(tmp_path):
    d = tmp_path / "RG-0014"
    d.mkdir()
    (d / "status.json").write_text(
        json.dumps({"sku": "RG-0014", "status": "sold",
                    "notes": "link square.link/u/WYk1Yl12 deactivated"}),
        encoding="utf-8",
    )
    (d / "label.json").write_text(json.dumps({"sku": "RG-0014"}), encoding="utf-8")
    recs = dpl.load_item_records(str(tmp_path))
    assert len(recs) == 1
    assert recs[0]["sku"] == "RG-0014"
    assert recs[0]["status"] == "sold"
    assert "wyk1yl12" in recs[0]["blob"]      # lowercased for case-insensitive scan
