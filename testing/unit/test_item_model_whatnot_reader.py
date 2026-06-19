from item_model.channels.whatnot_reader import build_whatnot_index, observe_whatnot
from item_model.models import Channel

CSV = (
    "Title,Price,SKU,Status\n"
    "Boogeyman 2 DVD,7,RG-0016,active\n"
    "Phantasm DVD,11,RG-0017,sold\n"
)


def test_index_and_observe(tmp_path):
    p = tmp_path / "whatnot-import.csv"
    p.write_text(CSV, encoding="utf-8")
    index = build_whatnot_index(str(p))

    o16 = observe_whatnot("RG-0016", index)
    assert o16.channel is Channel.WHATNOT and o16.present and o16.price == 7.0 and o16.sold is False

    o17 = observe_whatnot("RG-0017", index)
    assert o17.sold is True

    assert observe_whatnot("RG-9999", index).present is False
