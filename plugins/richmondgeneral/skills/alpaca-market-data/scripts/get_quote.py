#!/usr/bin/env python3
"""Get latest quote for a symbol from Alpaca."""

import sys
import os
import json
import requests
from datetime import datetime

# API Configuration
API_KEY = os.environ.get("ALPACA_API_KEY")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
BASE_URL = "https://data.alpaca.markets"

if not API_KEY or not SECRET_KEY:
    print("Error: ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set.", file=sys.stderr)
    sys.exit(1)

def get_quote(symbol: str) -> dict:
    """Get latest quote for a symbol."""
    headers = {
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY,
    }
    
    url = f"{BASE_URL}/v2/stocks/{symbol}/quotes/latest"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return response.json()

def format_quote(data: dict) -> str:
    """Format quote data for display."""
    quote = data.get("quote", {})
    
    # Format timestamp
    timestamp = quote.get("t", "")
    if timestamp:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    
    return f"""
Symbol: {data.get('symbol', 'N/A')}
Timestamp: {timestamp}

Bid: ${quote.get('bp', 0):.2f} x {quote.get('bs', 0):,}
Ask: ${quote.get('ap', 0):.2f} x {quote.get('as', 0):,}
Spread: ${(quote.get('ap', 0) - quote.get('bp', 0)):.2f}

Conditions: {', '.join(quote.get('c', []))}
Tape: {quote.get('z', 'N/A')}
"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python get_quote.py SYMBOL", file=sys.stderr)
        sys.exit(1)
    
    symbol = sys.argv[1].upper()
    
    try:
        data = get_quote(symbol)
        print(format_quote(data))
        
        # Also output JSON for programmatic use
        if "--json" in sys.argv:
            print("\n--- JSON ---")
            print(json.dumps(data, indent=2))
            
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
