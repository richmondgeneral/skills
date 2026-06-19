from item_model.channels.square_reader import observe_square
from item_model.models import Channel

def test_absent_sku_returns_not_present():
    index = {}  # sku -> (price_cents, sold_out)
    obs = observe_square("RG-9999", index=index)
    assert obs.channel is Channel.SQUARE and obs.present is False

def test_present_sku_maps_price_and_sold():
    index = {"RG-0009": (9500, False)}
    obs = observe_square("RG-0009", index=index)
    assert obs.present is True
    assert obs.price == 95.0
    assert obs.sold is False
