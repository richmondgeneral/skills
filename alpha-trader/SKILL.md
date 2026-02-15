---
name: alpha-trader
description: SPY options day trading and swing trading using 0DTE to 7DTE contracts. Execute trades via Alpaca API. Triggers on "trade SPY", "options play", "0DTE", "market setup", "buy calls", "buy puts", or AlphaTrader references.
version: 2.0.0
---

# AlphaTrader

Systematic SPY options trading for quick directional plays. Call/put buying only, no selling. Designed for volatile markets with headline-driven moves.

## Quick Reference

**Broker:** Alpaca (paper trading for POC, live for production)
**Instrument:** SPY options only
**Timeframes:** 0DTE to 7DTE
**Position Size:** $20-25 max per contract (POC phase)
**Win Rate Target:** 40% (2 of 5 trades)
**Risk/Reward:** Lose ~70% on losers, gain 150-300% on winners

---

## Technical Analysis Module (NEW)

### Available Indicators

| Category | Indicators |
|----------|------------|
| **Trend** | MACD, ADX, EMA (9/21/50), SMA (20/50/200), WMA |
| **Momentum** | RSI, Stochastic, CCI, Williams %R, ROC, MFI |
| **Volatility** | Bollinger Bands, ATR, Keltner Channels |
| **Volume** | VWAP, OBV, Volume Profile, Relative Volume |
| **Support/Resistance** | Pivot Points (Classic), Dynamic S/R |

### Signal Scoring System

Each indicator generates a BULLISH, BEARISH, or NEUTRAL signal. Signals are aggregated:

| Score | Interpretation |
|-------|----------------|
| 8+ Bullish | STRONG_BULLISH - High conviction long |
| 6-7 Bullish | BULLISH - Lean long |
| 4-5 Either | NEUTRAL - No clear edge |
| 6-7 Bearish | BEARISH - Lean short |
| 8+ Bearish | STRONG_BEARISH - High conviction short |

### Multi-Timeframe Analysis

Confluence across timeframes increases conviction:

| Timeframes | Alignment | Action |
|------------|-----------|--------|
| 1m, 5m, 15m, 30m | All agree | Full position |
| 3 of 4 agree | Lean | 75% position |
| 2 of 4 agree | Mixed | 50% or wait |
| All disagree | Conflict | No trade |

### Quick Commands

```
"SPY indicators"          → Run 5-min analysis
"multi-timeframe SPY"     → 1m/5m/15m/30m confluence
"full report SPY"         → Detailed all-indicator report
"check the MACD"          → Specific indicator check
```

---

## Data Caching (NEW)

### Cache Location
```
~/.alpha-trader/cache/
├── bars/           # OHLCV data by symbol/timeframe/date
├── options/        # Options chains by expiry
├── indicators/     # Pre-calculated indicator values
├── snapshots/      # Point-in-time market snapshots
└── metadata.json   # Cache index and stats
```

### Cache Behavior

| Data Type | Freshness | Auto-Refresh |
|-----------|-----------|--------------|
| 1-min bars | 1 minute | Yes |
| 5-min bars | 5 minutes | Yes |
| Daily bars | End of day | No |
| Options chain | 5 minutes | Yes |
| Indicators | 5 minutes | On request |

### Cache Commands

```
"cache stats"             → Show hit rate, size, file count
"clear old cache"         → Remove data older than 7 days
"invalidate SPY"          → Force refresh SPY data
```

---

## Core Strategy

### The Edge

This is NOT about being right on every trade. It's about:

1. **Asymmetric payoff**: Small losses, big wins
2. **Volatility is the product**: We need chaos, not calm
3. **Headlines > Fundamentals**: Trade the reaction, not the news
4. **Discipline > Prediction**: Follow the rules, ignore the ego

### Position Sizing (Bankroll Management)

| Phase | Contract Max | Max Open Positions | Bankroll Required |
|-------|--------------|-------------------|-------------------|
| POC | $25 | 2 | $200 |
| MVP | $50 | 3 | $500 |
| Scale | $100+ | 5 | $1000+ |

**Rule:** Never risk more than 12% of bankroll on single position.

### Win/Loss Math

```
Win rate: 40% (2 of 5)
Average winner: +150% (+$37.50 on $25)
Average loser: -70% (-$17.50 on $25)

Per 5 trades:
  Winners: 2 × $37.50 = +$75.00
  Losers:  3 × $17.50 = -$52.50
  Net: +$22.50 (19% return on capital deployed)
```

---

## Entry Rules

### Timing (All times Eastern)

| Time (ET) | Action |
|-----------|--------|
| 9:30-10:00 | AVOID - Wild spreads, price discovery |
| 10:00-11:30 | BEST ENTRIES - Morning dip window |
| 11:30-14:00 | Chop zone - Still acceptable |
| 14:00-15:00 | Dead zone - Can find bargains |
| 15:30-16:00 | AVOID - Spreads widen, MM reduce risk |

### Technical Entry Triggers

**For Calls (Bullish):**
- MACD histogram turning positive
- RSI < 40 bouncing (oversold recovery)
- Price above VWAP
- Stochastic bullish crossover from oversold
- Multi-TF confluence: 3+ timeframes bullish

**For Puts (Bearish):**
- MACD histogram turning negative
- RSI > 60 rolling over
- Price below VWAP
- Stochastic bearish crossover from overbought
- Multi-TF confluence: 3+ timeframes bearish

### Strike Selection

| Timeframe | Strike Selection | Target Delta |
|-----------|-----------------|--------------|
| 0DTE | 1-3 strikes OTM | 0.20-0.30 |
| 1DTE | 3-5 strikes OTM | 0.15-0.25 |
| 7DTE | 5-10 strikes OTM | 0.10-0.20 |

**Spread Rule:** Only trade strikes with $0.01-0.03 bid/ask spread.

---

## Exit Rules

### Winners

| Gain | Action |
|------|--------|
| +50% | Consider partial exit (sell half) |
| +100% | Move stop to breakeven |
| +150% | Take profits unless thesis strongly intact |
| +200%+ | Let it ride with trailing stop |

### Losers

| Loss | Action |
|------|--------|
| -50% | Re-evaluate thesis |
| -70% | MANDATORY EXIT - No exceptions |
| -100% | Should never happen if following rules |

### Technical Exit Triggers

- MACD crossover against position
- RSI reversal (overbought → turning down for calls)
- Break of key support/resistance
- VWAP cross against position
- Multi-TF divergence (higher TFs turning against)

---

## Averaging Down Rules

**ALLOWED:**
- Original thesis still valid
- Key support NOT broken
- Adding at same strike, lower price
- Total position still under 2x max size
- Technical indicators still supportive

**NOT ALLOWED:**
- Support/resistance broken
- MACD/RSI confirming reversal
- Just hoping it comes back
- Averaging into a different strike
- Would exceed position limits

---

## Alpaca Integration

### Real-Time Data Tools

| Tool | Use |
|------|-----|
| `get_stock_snapshot` | Current price + daily context |
| `get_stock_latest_quote` | Live bid/ask |
| `get_stock_bars` | Historical OHLCV for indicators |
| `get_option_chain` | Options pricing + Greeks |
| `get_option_latest_quote` | Real-time option prices |

### Order Execution

```
1. Run technical analysis (indicators + multi-TF)
2. Identify setup based on signals
3. Check options chain for target strike
4. Verify bid/ask spread (<$0.03)
5. Calculate position size ($25 max)
6. CONFIRM WITH USER before execution
7. Place limit order at mid-price
8. Monitor for fill
9. Log trade details
10. Set exit alerts
```

### Paper vs Live

| Mode | API Base URL |
|------|--------------|
| Paper | https://paper-api.alpaca.markets |
| Live | https://api.alpaca.markets |

**POC Phase = Paper Trading Only**

---

## Scripts Reference

### `/scripts/technical_indicators.py`

Main indicator calculation module.

```python
from technical_indicators import TechnicalAnalyzer, MultiTimeframeAnalyzer

# Single timeframe
analyzer = TechnicalAnalyzer(df)  # df with OHLCV
signals = analyzer.get_all_signals()
score = analyzer.score_signals()
report = analyzer.full_report()

# Multi-timeframe
mtf = MultiTimeframeAnalyzer({'1m': df1, '5m': df5, '15m': df15})
confluence = mtf.confluence_score()
```

### `/scripts/data_cache.py`

Local caching for market data.

```python
from data_cache import DataCache, SmartCache

cache = SmartCache()
cache.cache_bars('SPY', '5Min', df)
cached_df = cache.get_bars('SPY', '5Min')
stats = cache.get_cache_stats()
```

### `/scripts/analyze.py`

Command-line analysis runner.

```bash
python analyze.py SPY --test           # Quick analysis
python analyze.py SPY --test --multi   # Multi-TF
python analyze.py SPY --test --report  # Full report
```

---

## Risk Limits

**Hard Stops (Never Violate):**
- Max $25 per contract (POC)
- Max 2 open positions
- Max -70% loss per position
- No trading without user confirmation
- No trading first/last 30 minutes

**Soft Limits (Evaluate Case-by-Case):**
- Prefer 1DTE+ over 0DTE for overnight holds
- Prefer calls in uptrends, puts in downtrends
- Reduce size on consecutive losses
- Require multi-TF confluence for full size

---

## Failure Modes

What kills this strategy:

1. **Tilt:** Revenge trading after losses
2. **Overtrading:** Forcing setups that aren't there
3. **Moving stops:** Letting losers run past -70%
4. **FOMO:** Chasing moves already made
5. **Ego:** Needing to be "right" vs profitable
6. **Size creep:** Increasing position size after wins
7. **Indicator worship:** Ignoring context for signals

---

## Development Roadmap

### Phase 1: POC (Current) ✅
- Manual screenshots → Claude analysis
- User executes trades
- Prove thesis works

### Phase 2: MVP (In Progress) 🔄
- Alpaca MCP connection ✅
- Real-time data tools ✅
- Technical indicators ✅
- Local data cache ✅
- Claude executes with confirmation
- 20+ trade history logged

### Phase 3: Scale
- Increase position sizes
- Multiple simultaneous positions
- Automated alerts
- Performance analytics
- Streaming data integration

---

## References

- `scripts/technical_indicators.py` - Full indicator library
- `scripts/data_cache.py` - Local caching module
- `scripts/analyze.py` - CLI analysis runner
- `references/trade-log.md` - Historical trades
- `references/lessons-learned.md` - Post-mortems on losses
- `references/market-regimes.md` - Notes on different market conditions
