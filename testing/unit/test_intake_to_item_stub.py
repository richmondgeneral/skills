import os

import intake_to_item
from intake_to_item import resolve_staging_dir


def test_stub_has_attribute_fields():
    s = intake_to_item.stub_label("RG-0099")
    assert s["sku"] == "RG-0099"
    # new item-attribute fields, blank/defaults at stub time
    assert s["eye_color"] == ""
    assert s["measurements_in"] == {}          # filled during intake
    assert s["buyer_questions"] == []
    assert s["oversize"] is False
    # existing canonical schema preserved
    assert s["state"] == "Intake"
    assert set(s["channels"]) >= {"github_page", "square", "ebay", "whatnot", "marketplace"}


def test_default_staging_is_sibling_rg_pending(tmp_path):
    items = str(tmp_path / "items")
    d = resolve_staging_dir(items, "RG-0099")
    assert os.path.normpath(d) == os.path.normpath(str(tmp_path / "rg-pending" / "RG-0099"))


def test_never_inside_items_sku(tmp_path):
    items = str(tmp_path / "items")
    d = os.path.normpath(resolve_staging_dir(items, "RG-0099"))
    assert not d.startswith(os.path.normpath(os.path.join(items, "RG-0099")))


def test_override_respected(tmp_path):
    d = resolve_staging_dir(str(tmp_path / "items"), "RG-0099", staging_dir=str(tmp_path / "scratch"))
    assert os.path.normpath(d) == os.path.normpath(str(tmp_path / "scratch" / "RG-0099"))
