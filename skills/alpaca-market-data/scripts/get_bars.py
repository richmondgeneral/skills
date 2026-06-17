#!/usr/bin/env python3
"""Get historical bars for a symbol from Alpaca."""

import sys
import os
import json
import requests
from datetime import datetime
import argparse

# API Configuration
API_KEY = os.environ.get("ALPACA_API_KEY")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
BASE_URL = "https://data.alpaca.markets"

if not API_KEY or not SECRET_KEY:
    print("Error: ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set.", file=sys.stderr)
    sys.exit(1)

def get_bars(symbol: str, timeframe: str = "1Day", start: str = None, end: str = None, limit: int = 100) -> dict:
    """Get historical bars for a symbol."""
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY,
    }
    
    params = {
        "timeframe": timeframe,
        "limit": limit,
    }
    
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    
    url = f"{BASE_URL}/v2/stocks/{symbol}/bars"
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    
    return response.json()

def format_bars(data: dict) -> str:
    """Format bars data for display."""
    bars = data.get("bars", [])
    symbol = data.get("symbol", "N/A")
    
    output = [f"\n{symbol} - {len(bars)} bars\n"]
    output.append("=" * 80)
    output.append(f"{'Date':<20} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Volume':>15}")
    output.append("-" * 80)
    
    for bar in bars:
        timestamp = bar.get("t", "")
        if timestamp:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        output.append(
            f"{timestamp:<20} "
            f"{bar.get('o', 0):>10.2f} "
            f"{bar.get('h', 0):>10.2f} "
            f"{bar.get('l', 0):>10.2f} "
            f"{bar.get('c', 0):>10.2f} "
            f"{bar.get('v', 0):>15,}"
        )
    
    return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(description="Get historical bars from Alpaca")
    parser.add_argument("symbol", help="Stock symbol")
    parser.add_argument("--timeframe", default="1Day", help="Timeframe (1Min, 5Min, 15Min, 1Hour, 1Day, 1Week, 1Month)")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=100, help="Number of bars to return")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    args = parser.parse_args()
    
    try:
        data = get_bars(
            args.symbol.upper(),
            timeframe=args.timeframe,
            start=args.start,
            end=args.end,
            limit=args.limit
        )
        
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(format_bars(data))
            
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
