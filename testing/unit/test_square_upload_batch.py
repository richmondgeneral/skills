from pathlib import Path

from upload_batch import choose_preferred_variants, parse_bool, sort_upload_order


def test_choose_preferred_variants_prefers_nobg(tmp_path):
    original = tmp_path / "IMG_0001.jpg"
    nobg = tmp_path / "IMG_0001-nobg.png"
    other = tmp_path / "IMG_0002.jpg"

    for p in [original, nobg, other]:
        p.write_bytes(b"x")

    selected = choose_preferred_variants([original, nobg, other], prefer_nobg=True)
    selected_names = [p.name for p in selected]

    assert "IMG_0001-nobg.png" in selected_names
    assert "IMG_0001.jpg" not in selected_names
    assert "IMG_0002.jpg" in selected_names


def test_sort_upload_order_prefers_primary_then_hero(tmp_path):
    detail = tmp_path / "detail.jpg"
    hero = tmp_path / "hero.png"
    extra = tmp_path / "extra.jpg"

    for p in [detail, hero, extra]:
        p.write_bytes(b"x")

    ordered = sort_upload_order([detail, hero, extra], primary_file="extra.jpg")

    assert ordered[0].name == "extra.jpg"
    assert ordered[1].name == "hero.png"


def test_parse_bool_variants():
    assert parse_bool("true") is True
    assert parse_bool("YES") is True
    assert parse_bool("1") is True
    assert parse_bool("no") is False
    assert parse_bool("") is False
