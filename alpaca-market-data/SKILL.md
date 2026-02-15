---
name: alpaca-market-data
description: Real-time and historical market data for stocks/crypto via Alpaca API. Triggers on "stock price", "market data", "get quote".
allowed-tools: Read, Grep, Glob, Bash
metadata:
  version: "1.0"
  author: scottybe
  updated: "2026-02-14"
---

# Alpaca Market Data Skill

Real-time and historical market data from Alpaca Markets API.

## Purpose
Access live market data for stocks, options, and crypto without requiring a funded trading account.

## Features
- Real-time quotes (stocks, options, crypto)
- Historical bars (intraday, daily, weekly, monthly)
- Latest trades
- Market snapshots
- News feed

## API Keys
Uses live market data API keys (read-only, no trading).

## Usage

### Get Latest Quote
```bash
python scripts/get_quote.py AAPL
```

### Get Historical Bars
```bash
python scripts/get_bars.py AAPL --timeframe 1Day --start 2026-01-01
```

### Get Latest Trade
```bash
python scripts/get_trade.py AAPL
```

## Environment
Uses shared venv at `~/.claude/skills/.venv`
