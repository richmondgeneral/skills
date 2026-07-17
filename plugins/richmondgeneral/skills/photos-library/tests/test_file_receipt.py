import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import file_receipt as fr


def test_slugify_vendor():
    assert fr.slugify("Goodwill — Crystal Lake #2") == "goodwill-crystal-lake-2"


def test_slugify_degenerate_falls_back():
    assert fr.slugify("——") == "receipt"


def test_plan_receipt_names_basic():
    out = fr.plan_receipt_names(existing=set(), date="2026-07-15", vendor="Goodwill", count=2)
    assert out == ["2026-07-15-goodwill.jpeg", "2026-07-15-goodwill-2.jpeg"]


def test_plan_receipt_names_never_clobbers():
    existing = {"2026-07-15-goodwill.jpeg", "2026-07-15-goodwill-2.jpeg"}
    out = fr.plan_receipt_names(existing=existing, date="2026-07-15", vendor="Goodwill", count=1)
    assert out == ["2026-07-15-goodwill-3.jpeg"]


def test_append_ledger_creates_header_then_appends(tmp_path):
    log = tmp_path / "receipts-log.md"
    fr.append_ledger(str(log), date="2026-07-15", vendor="Goodwill", total="12.99",
                     lot="GIBA-C2", files=["2026-07-15-goodwill.jpeg"], uuids=["EA161386-C707"])
    text = log.read_text()
    assert text.startswith("# Receipts Log")
    assert "| 2026-07-15 | Goodwill | $12.99 | GIBA-C2 | 2026-07-15-goodwill.jpeg | EA161386-C707 |" in text
    fr.append_ledger(str(log), date="2026-07-16", vendor="Salvation Army", total=None,
                     lot=None, files=["a.jpeg", "b.jpeg"], uuids=["U1", "U2"])
    text = log.read_text()
    assert text.count("# Receipts Log") == 1
    assert "| 2026-07-16 | Salvation Army |  |  | a.jpeg, b.jpeg | U1, U2 |" in text
