from item_model.diff import diff_item
from item_model.models import (
    Channel, Severity, PageRecord, ChannelObservation,
)

def _page(**kw):
    return PageRecord(sku=kw.get("sku", "RG-0001"),
                      reference_price=kw.get("reference_price", 10.0),
                      sold=kw.get("sold", False),
                      listed_on=kw.get("listed_on", []),
                      intended_channel_prices=kw.get("intended_channel_prices", {}))

def test_no_findings_when_aligned():
    page = _page(reference_price=10.0)
    obs = [ChannelObservation(Channel.SQUARE, present=True, price=10.0, sold=False)]
    assert diff_item(page, obs) == []

def test_unintended_price_divergence_is_warning():
    page = _page(reference_price=95.0)
    obs = [ChannelObservation(Channel.SQUARE, present=True, price=45.0, sold=False)]
    findings = diff_item(page, obs)
    assert len(findings) == 1
    assert findings[0].field == "price"
    assert findings[0].severity is Severity.WARNING

def test_intended_override_suppresses_price_warning():
    page = _page(reference_price=7.0, intended_channel_prices={Channel.WHATNOT: 6.0})
    obs = [ChannelObservation(Channel.WHATNOT, present=True, price=6.0, sold=False)]
    assert diff_item(page, obs) == []

def test_sold_page_but_channel_active_is_critical():
    page = _page(sold=True)
    obs = [ChannelObservation(Channel.SQUARE, present=True, price=10.0, sold=False)]
    findings = diff_item(page, obs)
    assert any(f.field == "sold_state" and f.severity is Severity.CRITICAL
               for f in findings)

def test_channel_sold_but_page_active_is_critical():
    page = _page(sold=False)
    obs = [ChannelObservation(Channel.WHATNOT, present=True, price=10.0, sold=True)]
    findings = diff_item(page, obs)
    assert any(f.field == "sold_state" and f.severity is Severity.CRITICAL
               for f in findings)

def test_findings_sorted_critical_first():
    page = _page(reference_price=95.0, sold=False)
    obs = [
        ChannelObservation(Channel.SQUARE, present=True, price=45.0, sold=False),   # price WARNING (45 != 95)
        ChannelObservation(Channel.WHATNOT, present=True, price=95.0, sold=True),    # sold_state CRITICAL
    ]
    findings = diff_item(page, obs)
    assert len(findings) == 2
    assert findings[0].severity is Severity.CRITICAL
    assert findings[-1].severity is Severity.WARNING


def test_zero_intended_override_is_honored():
    page = _page(reference_price=7.0, intended_channel_prices={Channel.WHATNOT: 0.0})
    obs = [ChannelObservation(Channel.WHATNOT, present=True, price=0.0, sold=False)]
    assert diff_item(page, obs) == []
