from item_model.models import (
    Channel, Severity, PageRecord, ChannelObservation, DriftFinding,
)

def test_channel_and_severity_enums():
    assert Channel.SQUARE.value == "square"
    assert Channel.WHATNOT.value == "whatnot"
    assert Severity.CRITICAL.value == "critical"

def test_page_record_defaults():
    p = PageRecord(sku="RG-0009", reference_price=95.0)
    assert p.sold is False
    assert p.intended_channel_prices == {}

def test_channel_observation_and_finding():
    obs = ChannelObservation(channel=Channel.SQUARE, present=True, price=45.0, sold=False)
    assert obs.present and obs.price == 45.0
    f = DriftFinding(sku="RG-0009", field="price", channel=Channel.SQUARE,
                     severity=Severity.WARNING, expected=95.0, actual=45.0, message="x")
    assert f.severity is Severity.WARNING
    assert f.to_dict()["channel"] == "square"
