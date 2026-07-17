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


# ---------------------------------------------------------------------------
# Intake hardening (2026-07-15): resume manifest, verified tags, tag ordering.
# ---------------------------------------------------------------------------

def test_manifest_roundtrip_and_split(tmp_path):
    d = str(tmp_path)
    assert fc.load_manifest(d) == {}
    fc.save_manifest(d, {"u1": "hero.jpeg"})
    assert fc.load_manifest(d) == {"u1": "hero.jpeg"}
    photos = [{"uuid": "u1", "role": None}, {"uuid": "u2", "role": None}]
    already, todo = fc.split_filed({"u1": "hero.jpeg"}, photos)
    assert [p["uuid"] for p in already] == ["u1"]
    assert [p["uuid"] for p in todo] == ["u2"]


def test_load_manifest_tolerates_garbage(tmp_path):
    (tmp_path / fc.MANIFEST_NAME).write_text("not json")
    assert fc.load_manifest(str(tmp_path)) == {}


def test_parse_tag_result_mixed():
    ok, failed = fc.parse_tag_result("u1:ok\nu2:fail no media item\nu3:ok\n\n")
    assert ok == ["u1", "u3"]
    assert failed == {"u2": "no media item"}


def test_tag_sorted_retries_failures(monkeypatch):
    calls = []

    def fake_tag(keywords, uuids):
        calls.append(list(uuids))
        if len(calls) == 1:
            return ["u1"], {"u2": "flake"}
        return ["u2"], {}

    monkeypatch.setattr(fc, "tag_keywords", fake_tag)
    result = fc.tag_sorted("RG-0099", ["u1", "u2"])
    assert sorted(result["ok"]) == ["u1", "u2"]
    assert result["failed"] == {}
    assert calls == [["u1", "u2"], ["u2"]]  # retry hit only the failure


def test_add_to_album_failure_is_nonfatal(monkeypatch):
    import subprocess as sp

    def boom(*a, **k):
        raise sp.CalledProcessError(1, "osascript", stderr="AppleEvent timed out")

    monkeypatch.setattr(fc.subprocess, "run", boom)
    out = fc.add_to_album("RG-0099", ["u1"])
    assert out["ok"] is False and "non-fatal" in out["warning"]


# ---------------------------------------------------------------------------
# Duplicate-mint guard (RG-0060 void postmortem, 2026-07-15).
# ---------------------------------------------------------------------------

def _mk_item(tmp_path, sku, manifest):
    d = tmp_path / sku
    d.mkdir()
    (d / fc.MANIFEST_NAME).write_text(json.dumps(manifest))


def test_find_existing_sku_matches(tmp_path):
    _mk_item(tmp_path, "RG-0060", {"u1": "hero.jpeg", "u2": "detail-1.jpeg"})
    _mk_item(tmp_path, "RG-0061", {"u9": "hero.jpeg"})
    hits = fc.find_existing_sku(str(tmp_path), ["u2", "u3"])
    assert hits == {"RG-0060": ["u2"]}


def test_find_existing_sku_empty_when_no_match(tmp_path):
    _mk_item(tmp_path, "RG-0060", {"u1": "hero.jpeg"})
    assert fc.find_existing_sku(str(tmp_path), ["zz"]) == {}
    assert fc.find_existing_sku(str(tmp_path / "nope"), ["u1"]) == {}


def test_find_existing_sku_reports_conflict(tmp_path):
    _mk_item(tmp_path, "RG-0060", {"u1": "hero.jpeg"})
    _mk_item(tmp_path, "RG-0061", {"u2": "hero.jpeg"})
    hits = fc.find_existing_sku(str(tmp_path), ["u1", "u2"])
    assert set(hits) == {"RG-0060", "RG-0061"}


def test_find_existing_sku_skips_void_records(tmp_path):
    _mk_item(tmp_path, "RG-0060", {"u1": "hero.jpeg"})
    # real-world spelling: the actual RG-0060 record uses state "Voided"
    (tmp_path / "RG-0060" / "label.json").write_text('{"sku":"RG-0060","state":"Voided"}')
    _mk_item(tmp_path, "RG-0061", {"u1": "hero.jpeg"})
    hits = fc.find_existing_sku(str(tmp_path), ["u1"])
    assert hits == {"RG-0061": ["u1"]}  # void record ignored, live successor adopted
