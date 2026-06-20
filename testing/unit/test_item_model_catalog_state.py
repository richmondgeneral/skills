from item_model.catalog_state import build_catalog_state
from item_model.models import PageRecord, ChannelObservation, Channel


def test_build_snapshot_sorts_and_derives():
    recs = [
        (PageRecord(sku="RG-0002", reference_price=35.0, listed_on=[Channel.SQUARE]),
         [ChannelObservation(Channel.SQUARE, present=True, price=35.0, sold=False),
          ChannelObservation(Channel.WHATNOT, present=False)]),
        (PageRecord(sku="RG-0001", reference_price=19.5, sold=True, listed_on=[]),
         [ChannelObservation(Channel.SQUARE, present=True, price=19.5, sold=True)]),
    ]
    state = build_catalog_state(recs)
    assert state["item_count"] == 2
    assert [i["sku"] for i in state["items"]] == ["RG-0001", "RG-0002"]   # sorted
    rg2 = state["items"][1]
    assert rg2["reference_price"] == 35.0 and rg2["listed_on"] == ["square"]
    assert rg2["channels"]["square"] == {"present": True, "price": 35.0, "sold": False}
    assert rg2["channels"]["whatnot"]["present"] is False
    assert state["items"][0]["sold"] is True


def test_build_snapshot_empty():
    assert build_catalog_state([]) == {"item_count": 0, "items": []}


def test_snapshot_omits_unobserved_channel_key():
    # Positive-only Whatnot: the gatherer drops a None Whatnot observation (SKU absent from the
    # import CSV), so build_catalog_state gets no Whatnot obs for that item. It must NOT fabricate
    # a "whatnot" key — an unobserved channel is ABSENT from the snapshot, never present=false.
    # (listed_on still reflects the page's declared intent, even with no observation.)
    recs = [
        (PageRecord(sku="RG-0022", reference_price=32.0, listed_on=[Channel.WHATNOT]),
         [ChannelObservation(Channel.SQUARE, present=True, price=32.0, sold=False)]),
    ]
    item = build_catalog_state(recs)["items"][0]
    assert "whatnot" not in item["channels"]        # unobserved -> absent (not present:false)
    assert item["channels"]["square"]["present"] is True
    assert item["listed_on"] == ["whatnot"]          # page intent preserved despite no observation
