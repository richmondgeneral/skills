#!/usr/bin/env python3
"""
Quick Square customer lookup by phone number.
Outputs JSON with search request for Claude to use with Square MCP.

This script doesn't call Square directly - it generates the request
that Claude will execute via Square:make_api_request.

Usage:
  python3 lookup_customer.py +13124483219
  python3 lookup_customer.py 3124483219
  python3 lookup_customer.py "(312) 448-3219"

Output: JSON with normalized phone and Square search request
"""

import json
import sys
import re


def format_phone(phone):
    """
    Normalize phone to E.164 format for Square API.
    
    Square requires exact E.164 format (+1XXXXXXXXXX for US numbers).
    This handles common input variations.
    
    Examples:
      "3124483219" → "+13124483219"
      "13124483219" → "+13124483219"
      "(312) 448-3219" → "+13124483219"
      "+13124483219" → "+13124483219"
    """
    # Strip everything except digits
    digits = re.sub(r'[^\d]', '', phone)
    
    # Validate length
    if len(digits) < 10:
        raise ValueError(f"Phone number too short: {phone} ({len(digits)} digits)")
    if len(digits) > 15:
        raise ValueError(f"Phone number too long: {phone} ({len(digits)} digits)")
    
    # Normalize to E.164
    if len(digits) == 10:
        # US number without country code
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        # US number with country code
        return f"+{digits}"
    else:
        # International or other format
        return f"+{digits}"


def build_search_request(phone):
    """
    Build Square customer search request for phone lookup.
    
    Returns dict ready for Square:make_api_request with:
      service: "customers"
      method: "search"
    """
    return {
        "query": {
            "filter": {
                "phone_number": {
                    "exact": format_phone(phone)
                }
            }
        }
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: lookup_customer.py <phone_number>", file=sys.stderr)
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  python3 lookup_customer.py +13124483219", file=sys.stderr)
        print("  python3 lookup_customer.py 3124483219", file=sys.stderr)
        sys.exit(1)
    
    phone = sys.argv[1]
    
    try:
        normalized = format_phone(phone)
        request = build_search_request(phone)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Output JSON for Claude to use
    output = {
        "action": "search",
        "service": "customers",
        "method": "search",
        "request": request,
        "phone_input": phone,
        "phone_normalized": normalized
    }
    
    print(json.dumps(output, indent=2))
    
    # Also print MCP command example to stderr for reference
    print("", file=sys.stderr)
    print("# Use with Square MCP:", file=sys.stderr)
    print(f"# Square:make_api_request", file=sys.stderr)
    print(f"#   service='customers'", file=sys.stderr)
    print(f"#   method='search'", file=sys.stderr)
    print(f"#   request={json.dumps(request)}", file=sys.stderr)
