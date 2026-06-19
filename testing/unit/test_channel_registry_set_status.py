from item_model.channel_registry import set_channel_status


def test_sets_status_and_ids_preserving_others():
    label = {"sku": "RG-1", "channels": {"square": {"status": "pending", "object_id": None},
                                          "ebay": {"status": "not_listed"}}}
    out = set_channel_status(label, "square", "listed", object_id="ABC", buy_link="sq.link/x")
    assert out["channels"]["square"] == {"status": "listed", "object_id": "ABC", "buy_link": "sq.link/x"}
    assert out["channels"]["ebay"] == {"status": "not_listed"}     # untouched


def test_never_downgrades_a_sold_channel():
    label = {"sku": "RG-1", "channels": {"square": {"status": "sold"}}}
    out = set_channel_status(label, "square", "listed")
    assert out["channels"]["square"]["status"] == "sold"          # sold is sticky


def test_channel_absent_from_registry_is_created():
    label = {"sku": "RG-1", "channels": {"square": {"status": "listed"}}}
    out = set_channel_status(label, "ebay", "listed", item_id="123")
    assert out["channels"]["ebay"] == {"status": "listed", "item_id": "123"}
    assert out["channels"]["square"] == {"status": "listed"}       # untouched


def test_does_not_mutate_caller_input():
    label = {"sku": "RG-1", "channels": {"square": {"status": "pending"}}}
    out = set_channel_status(label, "square", "listed", object_id="ABC")
    assert label["channels"]["square"] == {"status": "pending"}    # original unchanged
    assert out is not label
