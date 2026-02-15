#!/usr/bin/env python3
"""
Parse contacts.md and output JSON of customers ready for Square sync.
Claude uses this output to make Square API calls via MCP.

DEPENDENCY: Requires ~/.claude/skills/contacts-manager/references/contacts.md
            with "## Detailed Profiles - Richmond General Customers" section.

Usage:
  python3 parse_contacts.py                    # All customers
  python3 parse_contacts.py --category Lead    # Filter by category
  python3 parse_contacts.py --phone +1234...   # Single contact
  python3 parse_contacts.py --validate         # Check for issues
"""

import json
import re
import sys
import os

# Path to contacts file - update if contacts-manager skill moves
CONTACTS_FILE = os.path.expanduser('~/.claude/skills/contacts-manager/references/contacts.md')

# Square Customer Group IDs for Richmond General
# These were created Dec 2025 and map to relationship types
GROUP_IDS = {
    # Categories (from contacts.md Category field)
    'Customer': None,      # General customers, no special group
    'Lead': None,          # Prospects, not yet grouped
    'Partner': None,       # Business partners, grouped by type below
    'Nurture': None,       # Relationship maintenance only
    
    # Interest-based groups (detected from Interest/Status fields)
    'Vinyl': '4A4AG6K8CYAYC7T2HSE2R04EJE',      # Record collectors
    'Estate': '1HR6MC66JXVC5A1XS7137W7DAX',     # Estate cleanout sources
    'Reseller': '34THMX8DN921VQ04KGHV7KZ0AA',  # eBay/resale partners
    'VIP': '6NGXFHDNJ6MVEFMJKXE8PZ8VMZ',        # High-value repeat customers
    'Trade': '7XP6P4G6KDYQZ32HHCRNH9RJKM',      # Barter/trade relationships
}


def validate_phone(phone):
    """
    Validate and normalize phone number to E.164 format.
    Returns (normalized_phone, error_message) tuple.
    """
    if not phone:
        return None, "No phone number"
    
    # Strip non-digits
    digits = re.sub(r'[^\d]', '', phone)
    
    if len(digits) < 10:
        return None, f"Phone too short: {phone}"
    if len(digits) > 15:
        return None, f"Phone too long: {phone}"
    
    # Normalize to E.164
    if len(digits) == 10:
        return f"+1{digits}", None
    elif len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}", None
    else:
        return f"+{digits}", None


def parse_contacts():
    """
    Parse contacts.md for Richmond General customers.
    Returns list of customer dicts with Square-ready data.
    """
    # Check file exists
    if not os.path.exists(CONTACTS_FILE):
        print(f"ERROR: Contacts file not found: {CONTACTS_FILE}", file=sys.stderr)
        print("Make sure contacts-manager skill is installed.", file=sys.stderr)
        sys.exit(1)
    
    with open(CONTACTS_FILE, 'r') as f:
        content = f.read()
    
    # Find the Richmond General Customers section
    section = re.search(
        r'## Detailed Profiles - Richmond General Customers\n(.+?)(?=\n---\n## |\n---\n\n## |$)', 
        content, 
        re.DOTALL
    )
    
    if not section:
        print("ERROR: Could not find 'Richmond General Customers' section", file=sys.stderr)
        return []
    
    customers = []
    validation_errors = []
    profiles = re.split(r'\n### ', section.group(1))
    
    for profile in profiles:
        if not profile.strip():
            continue
        
        lines = profile.strip().split('\n')
        raw_name = lines[0].strip()
        
        # Parse name - handle formats like:
        # "414 Contact (GET NAME!)" → given_name="414", family_name="Contact"
        # "Bill North - North Construction" → given_name="Bill", family_name="North"
        name = re.sub(r'\s*\([^)]*\)\s*', '', raw_name)  # Remove parenthetical
        name = re.split(r'\s*-\s*', name)[0].strip()  # Take first part before dash
        
        name_parts = name.split()
        given_name = name_parts[0] if name_parts else ''
        family_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
        
        customer = {
            'raw_name': raw_name,
            'given_name': given_name,
            'family_name': family_name,
            'phone': None,
            'phone_error': None,
            'category': None,
            'interest': None,
            'promise': None,
            'waiting': None,
            'status': None,
            'note_parts': [],
            'group_ids': [],
        }
        
        # Parse structured fields from markdown
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('- **Phone**:'):
                raw_phone = re.search(r'\+\d+', line)
                if raw_phone:
                    phone, error = validate_phone(raw_phone.group())
                    customer['phone'] = phone
                    customer['phone_error'] = error
            elif line.startswith('- **Category**:'):
                customer['category'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Interest**:'):
                customer['interest'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Promise**:'):
                val = line.split(':', 1)[1].strip()
                if val.lower() != 'null':
                    customer['promise'] = val
            elif line.startswith('- **Waiting**:'):
                val = line.split(':', 1)[1].strip()
                if val.lower() != 'null':
                    customer['waiting'] = val
            elif line.startswith('- **Status**:'):
                customer['status'] = line.split(':', 1)[1].strip()
            elif line.startswith('- **Note**:'):
                customer['note_parts'].append(line.split(':', 1)[1].strip())
            elif line.startswith('- **Wants**:'):
                customer['note_parts'].append(f"Wants: {line.split(':', 1)[1].strip()}")
        
        # Build Square note in consistent format
        note_lines = []
        if customer['category']:
            note_lines.append(f"[{customer['category']}]")
        if customer['interest']:
            note_lines.append(f"Interest: {customer['interest']}")
        if customer['status']:
            note_lines.append(f"Status: {customer['status']}")
        if customer['promise']:
            note_lines.append(f"Promise: {customer['promise']}")
        if customer['waiting']:
            note_lines.append(f"Waiting: {customer['waiting']}")
        for note in customer['note_parts']:
            note_lines.append(note)
        note_lines.append("Source: iMessage contact")
        
        customer['square_note'] = '\n'.join(note_lines)
        
        # Determine group IDs based on category and interests
        # Groups are assigned by detecting keywords in interest/status/note fields
        cat = customer['category'] or ''
        interest = (customer['interest'] or '').lower()
        status = (customer['status'] or '').lower()
        all_notes = ' '.join(customer['note_parts']).lower()
        searchable = f"{interest} {status} {all_notes}"
        
        if 'vinyl' in searchable or 'record' in searchable:
            customer['group_ids'].append(GROUP_IDS['Vinyl'])
        if 'estate' in searchable:
            customer['group_ids'].append(GROUP_IDS['Estate'])
        if 'resell' in searchable or 'ebay' in searchable:
            customer['group_ids'].append(GROUP_IDS['Reseller'])
        if 'trade' in searchable:
            customer['group_ids'].append(GROUP_IDS['Trade'])
        
        # Filter out None group IDs
        customer['group_ids'] = [g for g in customer['group_ids'] if g]
        
        # Build reference_id for bidirectional linking
        if customer['phone']:
            customer['reference_id'] = f"imessage:{customer['phone']}"
        
        # Track validation errors
        if customer['phone_error']:
            validation_errors.append(f"{raw_name}: {customer['phone_error']}")
        
        # Only include contacts with valid phone numbers
        if customer['phone']:
            customers.append(customer)
    
    # Report validation errors to stderr
    if validation_errors:
        print("Validation warnings:", file=sys.stderr)
        for err in validation_errors:
            print(f"  - {err}", file=sys.stderr)
    
    return customers


def format_for_square(customer):
    """
    Format customer dict for Square API create request.
    Returns dict ready to pass to mcp_square_api:make_api_request.
    """
    req = {
        'given_name': customer['given_name'],
        'phone_number': customer['phone'],
        'note': customer['square_note'],
    }
    if customer['family_name']:
        req['family_name'] = customer['family_name']
    if customer.get('reference_id'):
        req['reference_id'] = customer['reference_id']
    return req


if __name__ == '__main__':
    # Handle --validate flag
    if '--validate' in sys.argv:
        customers = parse_contacts()
        print(f"Found {len(customers)} valid customers")
        for c in customers:
            groups = ', '.join(c['group_ids']) if c['group_ids'] else 'none'
            print(f"  {c['raw_name']}: {c['phone']} → groups: {groups}")
        sys.exit(0)
    
    customers = parse_contacts()
    
    # Filter by category
    if '--category' in sys.argv:
        try:
            idx = sys.argv.index('--category')
            cat = sys.argv[idx + 1]
            customers = [c for c in customers if c['category'] == cat]
        except IndexError:
            print("ERROR: --category requires a value", file=sys.stderr)
            sys.exit(1)
    
    # Filter by phone
    if '--phone' in sys.argv:
        try:
            idx = sys.argv.index('--phone')
            phone = sys.argv[idx + 1]
            phone_digits = re.sub(r'[^\d]', '', phone)
            customers = [c for c in customers if phone_digits in (c['phone'] or '')]
        except IndexError:
            print("ERROR: --phone requires a value", file=sys.stderr)
            sys.exit(1)
    
    # Output JSON for Claude to use
    output = []
    for c in customers:
        output.append({
            'name': c['raw_name'],
            'phone': c['phone'],
            'category': c['category'],
            'square_request': format_for_square(c),
            'group_ids': c['group_ids'],
        })
    
    print(json.dumps(output, indent=2))
