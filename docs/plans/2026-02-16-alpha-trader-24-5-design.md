# Alpha-Trader 24/5 Extension Design

**Date:** 2026-02-16
**Author:** scottybe + Claude
**Version:** alpha-trader 2.0.0 → 3.0.0

## Summary

Extend `alpha-trader` to support 24/5 overnight equity trading via Alpaca's Trading API. This adds any NMS equity as a tradeable instrument during overnight, pre-market, and after-hours sessions alongside the existing SPY options strategy during regular hours.

## Approach

Single SKILL.md extension (Approach 1). Add parallel sections for overnight equities directly to `alpha-trader/SKILL.md`, plus new scripts for session awareness and overnight asset screening.

## Session Schedule

| Session | Hours (ET) | Instruments | Order Types |
|---------|-----------|-------------|-------------|
| Overnight | 8:00 PM - 4:00 AM | NMS equities only | Limit only, `extended_hours=True` |
| Pre-market | 4:00 AM - 9:30 AM | NMS equities only | Limit only, `extended_hours=True` |
| Regular | 9:30 AM - 4:00 PM | SPY options + equities | All order types |
| After-hours | 4:00 PM - 8:00 PM | NMS equities only | Limit only, `extended_hours=True` |

Follows NYSE holiday calendar. Closed when US markets are fully closed for holidays.

## Overnight Equity Strategy

### Position Sizing

| Phase | Max Per Position | Max Open Positions | Bankroll Required |
|-------|-----------------|-------------------|-------------------|
| POC | $200 | 2 | $1,000 |
| MVP | $500 | 3 | $2,500 |
| Scale | $1,000+ | 5 | $5,000+ |

### Entry Strategies

**News/Catalyst:**
- Earnings miss/beat after hours: fade or follow depending on magnitude
- Breaking macro news (Fed, geopolitical): directional play on affected sectors
- Volume confirmation: overnight volume > 2x average overnight volume for that stock
- Verify `overnight_tradable=True` via Assets API before entry

**Gap Trading:**
- Stocks gapping >2% from prior close during overnight/pre-market
- Enter in direction of gap if volume-supported, fade if exhaustion signals
- Technical confirmation via RSI, VWAP from overnight data feed

**Position Management:**
- Hedge existing options positions with equity during overnight
- Scale into equity positions at better prices when spreads allow
- Exit equity positions overnight to lock in gains before regular session repricing

### Exit Rules

| Condition | Action |
|-----------|--------|
| +5% gain | Take partial profits (sell half) |
| +10% gain | Trail with 3% stop |
| -3% loss | Re-evaluate thesis |
| -5% loss | MANDATORY EXIT |
| Session transition (overnight -> pre-market) | Re-evaluate all positions |

### Spread/Liquidity Guard

- Max bid-ask spread: 0.5% of stock price
- If spread exceeds threshold, do NOT enter
- Log spread at entry for post-trade analysis

## API Integration

### Order Parameters (Overnight/Extended)

```python
place_stock_order(
    symbol="NVDA",
    side="buy",
    quantity=5,
    type="limit",              # MUST be limit
    limit_price=135.50,
    time_in_force="day",       # Only TIF supported overnight (GTC coming later)
    extended_hours=True         # REQUIRED for non-regular-hours orders
)
```

### Pre-flight Checks (Every Order)

1. `session_manager.get_current_session()` - confirm session allows equities
2. `get_asset(symbol)` - verify `overnight_tradable=True` and `overnight_halted=False`
3. `overnight_screener.check_spread(symbol)` - verify bid-ask within 0.5% guard
4. `get_account_info()` - verify buying power (2x margin max overnight, no DTBP)
5. Confirm order is `type="limit"` and `extended_hours=True`

### Margin Rules

| Session | Max Buying Power |
|---------|-----------------|
| Regular hours | 4x DTBP (if PDT) |
| Extended hours (pre/post) | 2x |
| Overnight | 2x (DTBP does not apply) |

At 8:00 PM ET session transition, orders using DTBP-level margin may get rejected. Session manager warns at 7:45 PM ET.

### PDT Awareness

- Opening + closing on same assigned trade date = day trade
- 8:00 PM - 11:59 PM trades assigned to NEXT calendar day
- 12:00 AM - 4:00 AM trades assigned to CURRENT day
- Session manager tracks assigned trade dates to warn before triggering PDT

## Market Data

### Overnight Data Feed

- `feed=DataFeed.OVERNIGHT` (basic plan)
- `feed=boats` (Algo Trader Plus)
- Applies to Latest Quotes, Bars, Trades during 8:00 PM - 4:00 AM ET
- Historical data older than 15 minutes: use `feed=boats`

### Cache Freshness (Overnight Additions)

- Overnight quotes: 120s (wider due to lower liquidity)
- Overnight bars: 300s
- Asset eligibility list: 3600s (changes are rare)

## New Scripts

### `scripts/session_manager.py`

- `get_current_session()` - returns session name, allowed instruments, order constraints
- `get_next_session()` - what's coming and when
- `is_market_open()` - accounts for NYSE holiday calendar
- `get_session_for_time(dt)` - given a datetime, return session info
- Uses Alpaca `get_clock` and `get_calendar` MCP tools

### `scripts/overnight_screener.py`

- `get_overnight_eligible()` - query Assets API, filter `overnight_tradable=True`, exclude `overnight_halted=True`
- `screen_movers(threshold_pct=2.0)` - find stocks moving >N% from prior close
- `check_spread(symbol)` - verify bid-ask within 0.5% liquidity guard
- `get_overnight_volume(symbol)` - compare current overnight volume to average
- Optimal sync window: 7:45-8:00 PM ET

## Modified Files

### `scripts/data_cache.py`

Add overnight freshness thresholds to `SmartCache.FRESHNESS` dict.

### `alpha-trader/SKILL.md`

**Updated structure:**

1. Quick Reference (updated for 24/5)
2. Session Schedule (NEW)
3. Technical Analysis Module (unchanged)
4. SPY Options Strategy (renamed from Core Strategy)
5. SPY Options Entry Rules (renamed)
6. SPY Options Exit Rules (renamed)
7. 24/5 Equity Strategy (NEW)
8. 24/5 Equity Entry Rules (NEW)
9. 24/5 Equity Exit Rules (NEW)
10. 24/5 API Reference (NEW)
11. Averaging Down Rules (unchanged, applies to both)
12. Risk Limits (updated for equity limits)
13. Development Roadmap (updated phases)

**New trigger keywords in frontmatter:**
`"overnight trading"`, `"24/5"`, `"extended hours"`, `"after hours"`, `"pre-market"`, `"overnight equities"`

**Version bump:** 2.0.0 -> 3.0.0 (major: new instrument class)

## Unchanged Files

- `scripts/technical_indicators.py` - works on any OHLCV DataFrame
- `scripts/analyze.py` - overnight bars feed in same format

## Sources

- [Alpaca 24/5 Trading Docs](https://docs.alpaca.markets/docs/245-trading)
- [How to Trade 24/5 with Alpaca](https://alpaca.markets/learn/how-to-trade-us-stocks-24_5-overnight-with-python-and-alpaca)
- [Alpaca 24/5 Launch Blog](https://alpaca.markets/blog/introducing-stocks-24_5-overnight-with-alpaca-trading-api/)
