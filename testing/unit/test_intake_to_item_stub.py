import intake_to_item


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
