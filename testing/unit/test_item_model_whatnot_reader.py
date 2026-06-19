from item_model.channels.whatnot_reader import build_whatnot_index, observe_whatnot
from item_model.models import Channel

# Production schema: has `Price`, NO `Status` column (see items/rg-inventory/whatnot-import.csv).
PROD_CSV = (
    "Category,Title,Quantity,Type,Price,SKU\n"
    "DVDs & Movies,Boogeyman 2 DVD,1,Buy it Now,7,RG-0016\n"
    "DVDs & Movies,Phantasm DVD,1,Buy it Now,11,RG-0017\n"
)

# Generator schema: StartingPrice/BuyItNowPrice (no `Price`), and a `Status` column.
GENERATOR_CSV = (
    "Title,StartingPrice,BuyItNowPrice,SKU,Status\n"
    "Boogeyman 2 DVD,5,7,RG-0016,active\n"
    "Phantasm DVD,8,11,RG-0017,sold\n"
)


def test_prod_schema_price_parses_and_sold_is_none(tmp_path):
    """Production CSV has Price but no Status -> price parses, sold must be None
    (channel does not expose sold-state; the diff engine skips the sold check)."""
    p = tmp_path / "whatnot-import.csv"
    p.write_text(PROD_CSV, encoding="utf-8")
    index = build_whatnot_index(str(p))

    o16 = observe_whatnot("RG-0016", index)
    assert o16.channel is Channel.WHATNOT
    assert o16.present is True
    assert o16.price == 7.0
    assert o16.sold is None

    # Absent SKU -> None: the CSV is positive-only (it can affirm a listing, not deny
    # one — items listed via the Whatnot UI never appear in the import CSV), so absence
    # yields no observation rather than a false present=False.
    assert observe_whatnot("RG-9999", index) is None


def test_status_column_present_sets_bool_sold(tmp_path):
    """When a Status column exists, sold is a bool: True for 'sold', False for 'active'."""
    p = tmp_path / "whatnot-import.csv"
    p.write_text(GENERATOR_CSV, encoding="utf-8")
    index = build_whatnot_index(str(p))

    o16 = observe_whatnot("RG-0016", index)
    assert o16.sold is False

    o17 = observe_whatnot("RG-0017", index)
    assert o17.sold is True


def test_buyitnow_price_fallback(tmp_path):
    """No `Price` column -> price falls back to BuyItNowPrice."""
    csv = (
        "Title,StartingPrice,BuyItNowPrice,SKU,Status\n"
        "Boogeyman 2 DVD,5,7,RG-0016,active\n"
    )
    p = tmp_path / "whatnot-import.csv"
    p.write_text(csv, encoding="utf-8")
    index = build_whatnot_index(str(p))

    o16 = observe_whatnot("RG-0016", index)
    assert o16.price == 7.0
