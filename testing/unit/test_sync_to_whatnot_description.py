"""
Regression for sync_to_whatnot._build_description: the join character must
be a real newline (\n), not the two-character escape sequence ('\\n').

The pre-fix code wrote `"\\\\n".join(lines)` which produced the literal
two-character sequence backslash-n in the Whatnot CSV Description column,
displaying verbatim to buyers.
"""
from sync_to_whatnot import LabelRecord, _build_description


def _make_record(**overrides):
    base = dict(
        product_name="Test Product",
        attributes="1970 • Book",
        price=20.0,
        condition="Very Good",
        condition_notes="Minor edge wear",
        sku="RG-0001",
        qr_code_url="https://richmondgeneral.github.io/items/RG-0001/",
    )
    base.update(overrides)
    return LabelRecord(**base)


def test_description_separator_is_real_newline():
    desc = _build_description(_make_record())
    # The literal two-char escape must NOT appear.
    assert "\\n" not in desc, (
        f"description contains literal backslash-n: {desc!r}")
    # Real newlines DO appear (one per joined line).
    assert "\n" in desc


def test_description_lines_are_separately_renderable():
    """Splitting on real newline must yield each segment as its own line."""
    desc = _build_description(_make_record())
    lines = desc.split("\n")
    assert lines[0] == "Test Product"
    assert any("Attributes:" in line for line in lines)
    assert any("Condition: Very Good" in line for line in lines)
    assert any("Condition Notes:" in line for line in lines)
    assert any("More details:" in line for line in lines)


def test_description_omits_optional_lines_when_missing():
    desc = _build_description(_make_record(attributes="", condition_notes="",
                                           qr_code_url=""))
    lines = desc.split("\n")
    assert lines[0] == "Test Product"
    assert "Attributes:" not in desc
    assert "Condition Notes:" not in desc
    assert "More details:" not in desc
