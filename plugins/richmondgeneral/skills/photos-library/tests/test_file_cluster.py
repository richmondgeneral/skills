import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import file_cluster as fc


def test_resolve_sku_explicit_ok():
    assert fc.resolve_sku("RG-0031", mint=False, allocate=None) == "RG-0031"


def test_resolve_sku_rejects_bad_format():
    import pytest
    with pytest.raises(ValueError):
        fc.resolve_sku("0031", mint=False, allocate=None)


def test_resolve_sku_mint_calls_allocator():
    assert fc.resolve_sku(None, mint=True, allocate=lambda: "RG-0099") == "RG-0099"


def test_plan_filenames_hero_when_absent():
    out = fc.plan_filenames(existing=set(), photos=[{"uuid": "u1", "role": "hero"}])
    assert out == [{"uuid": "u1", "out": "hero.jpeg"}]


def test_plan_filenames_hero_demoted_when_present():
    out = fc.plan_filenames(existing={"hero.png"}, photos=[{"uuid": "u1", "role": "hero"}])
    assert out == [{"uuid": "u1", "out": "detail-1.jpeg"}]


def test_plan_filenames_named_detail_and_collision():
    out = fc.plan_filenames(existing={"detail-back.jpeg"},
                            photos=[{"uuid": "u1", "role": "detail-back"},
                                    {"uuid": "u2", "role": None}])
    assert out[0]["out"] == "detail-back-2.jpeg"
    assert out[1]["out"] == "detail-1.jpeg"


def test_stub_label_written_only_when_absent(tmp_path):
    d = tmp_path / "RG-0031"
    d.mkdir()
    fc.ensure_label(str(d), "RG-0031")
    data = json.loads((d / "label.json").read_text())
    assert data["sku"] == "RG-0031"
    (d / "label.json").write_text('{"sku":"RG-0031","price":"42"}')
    fc.ensure_label(str(d), "RG-0031")  # must not clobber
    assert json.loads((d / "label.json").read_text())["price"] == "42"
