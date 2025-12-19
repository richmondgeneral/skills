#!/usr/bin/env python3
"""
Sync customer data to Apple Contacts.

Updates Apple Contacts with data from Square CRM (last name, alt phone, notes).
Claude calls Square first to get customer data, then runs this script.

Usage:
  # Update last name
  python3 sync_to_apple_contacts.py +13129143889 --last-name "Giba"
  
  # Add alternate phone
  python3 sync_to_apple_contacts.py +13129143889 --alt-phone "+17085970480"
  
  # Add/update note
  python3 sync_to_apple_contacts.py +13129143889 --note "Square signup Dec 18"
  
  # All at once
  python3 sync_to_apple_contacts.py +13129143889 --last-name "Giba" --alt-phone "+17085970480" --note "VIP customer"
  
  # From JSON (for Claude pipeline)
  python3 sync_to_apple_contacts.py --json '{"phone": "+13129143889", "last_name": "Giba", "alt_phone": "+17085970480"}'

Output: Success/failure message
"""

import argparse
import json
import re
import subprocess
import sys


def format_phone(phone):
    """Normalize phone to E.164 format."""
    digits = re.sub(r'[^\d]', '', phone)
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    else:
        return f"+{digits}"


def run_applescript(script):
    """Run AppleScript and return result."""
    result = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise Exception(f"AppleScript error: {result.stderr}")
    return result.stdout.strip()


def find_contact_by_phone(phone):
    """Find contact in Apple Contacts by phone number. Returns name or None."""
    normalized = format_phone(phone)
    # Try with and without formatting
    script = f'''
    tell application "Contacts"
        set matchingPeople to (every person whose value of phones contains "{normalized}")
        if (count of matchingPeople) > 0 then
            set p to first item of matchingPeople
            return name of p
        else
            return "NOT_FOUND"
        end if
    end tell
    '''
    result = run_applescript(script)
    return None if result == "NOT_FOUND" else result


def update_last_name(phone, last_name):
    """Update contact's last name."""
    normalized = format_phone(phone)
    script = f'''
    tell application "Contacts"
        set matchingPeople to (every person whose value of phones contains "{normalized}")
        if (count of matchingPeople) > 0 then
            set p to first item of matchingPeople
            set last name of p to "{last_name}"
            save
            return "OK: " & name of p
        else
            return "NOT_FOUND"
        end if
    end tell
    '''
    return run_applescript(script)


def update_first_name(phone, first_name):
    """Update contact's first name."""
    normalized = format_phone(phone)
    script = f'''
    tell application "Contacts"
        set matchingPeople to (every person whose value of phones contains "{normalized}")
        if (count of matchingPeople) > 0 then
            set p to first item of matchingPeople
            set first name of p to "{first_name}"
            save
            return "OK: " & name of p
        else
            return "NOT_FOUND"
        end if
    end tell
    '''
    return run_applescript(script)


def add_alt_phone(phone, alt_phone, label="other"):
    """Add alternate phone number to contact."""
    normalized = format_phone(phone)
    alt_normalized = format_phone(alt_phone)
    script = f'''
    tell application "Contacts"
        set matchingPeople to (every person whose value of phones contains "{normalized}")
        if (count of matchingPeople) > 0 then
            set p to first item of matchingPeople
            -- Check if alt phone already exists
            set existingPhones to value of phones of p
            if "{alt_normalized}" is not in existingPhones then
                make new phone at end of phones of p with properties {{label:"{label}", value:"{alt_normalized}"}}
                save
                return "ADDED: {alt_normalized}"
            else
                return "EXISTS: {alt_normalized}"
            end if
        else
            return "NOT_FOUND"
        end if
    end tell
    '''
    return run_applescript(script)


def update_note(phone, note):
    """Update or append to contact's note."""
    normalized = format_phone(phone)
    # Escape quotes and newlines for AppleScript
    safe_note = note.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    script = f'''
    tell application "Contacts"
        set matchingPeople to (every person whose value of phones contains "{normalized}")
        if (count of matchingPeople) > 0 then
            set p to first item of matchingPeople
            set currentNote to note of p
            if currentNote is missing value then
                set note of p to "{safe_note}"
            else
                set note of p to currentNote & "\\n" & "{safe_note}"
            end if
            save
            return "OK: note updated"
        else
            return "NOT_FOUND"
        end if
    end tell
    '''
    return run_applescript(script)


def add_company(phone, company):
    """Set contact's company/organization."""
    normalized = format_phone(phone)
    safe_company = company.replace('"', '\\"')
    script = f'''
    tell application "Contacts"
        set matchingPeople to (every person whose value of phones contains "{normalized}")
        if (count of matchingPeople) > 0 then
            set p to first item of matchingPeople
            set organization of p to "{safe_company}"
            save
            return "OK: company set to {safe_company}"
        else
            return "NOT_FOUND"
        end if
    end tell
    '''
    return run_applescript(script)


def sync_from_json(json_data):
    """
    Sync contact from JSON data (for Claude pipeline).
    
    Expected JSON format:
    {
        "phone": "+13129143889",        # Required - lookup key
        "first_name": "Mike",           # Optional
        "last_name": "Giba",            # Optional
        "alt_phone": "+17085970480",    # Optional
        "company": "Some Corp",         # Optional
        "note": "Square signup Dec 18"  # Optional
    }
    """
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data
    
    phone = data.get('phone')
    if not phone:
        raise ValueError("phone is required in JSON data")
    
    results = []
    
    # Check contact exists first
    existing = find_contact_by_phone(phone)
    if not existing:
        results.append(f"❌ Contact not found for {phone}")
        return results
    
    results.append(f"📱 Found: {existing}")
    
    # Apply updates
    if data.get('first_name'):
        r = update_first_name(phone, data['first_name'])
        results.append(f"  First name: {r}")
    
    if data.get('last_name'):
        r = update_last_name(phone, data['last_name'])
        results.append(f"  Last name: {r}")
    
    if data.get('alt_phone'):
        r = add_alt_phone(phone, data['alt_phone'])
        results.append(f"  Alt phone: {r}")
    
    if data.get('company'):
        r = add_company(phone, data['company'])
        results.append(f"  Company: {r}")
    
    if data.get('note'):
        r = update_note(phone, data['note'])
        results.append(f"  Note: {r}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Sync customer data to Apple Contacts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s +13129143889 --last-name "Giba"
  %(prog)s +13129143889 --alt-phone "+17085970480" --note "VIP"
  %(prog)s --json '{"phone": "+13129143889", "last_name": "Giba"}'
        '''
    )
    
    parser.add_argument('phone', nargs='?', help='Phone number to look up')
    parser.add_argument('--last-name', help='Set last name')
    parser.add_argument('--first-name', help='Set first name')
    parser.add_argument('--alt-phone', help='Add alternate phone number')
    parser.add_argument('--company', help='Set company/organization')
    parser.add_argument('--note', help='Add to notes')
    parser.add_argument('--json', help='JSON data with all fields')
    parser.add_argument('--check', action='store_true', help='Just check if contact exists')
    
    args = parser.parse_args()
    
    # JSON mode
    if args.json:
        try:
            results = sync_from_json(args.json)
            for r in results:
                print(r)
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Phone required for non-JSON mode
    if not args.phone:
        parser.print_help()
        sys.exit(1)
    
    phone = args.phone
    
    # Check mode
    if args.check:
        result = find_contact_by_phone(phone)
        if result:
            print(f"✅ Found: {result}")
        else:
            print(f"❌ Not found: {phone}")
        sys.exit(0 if result else 1)
    
    # Apply individual updates
    results = []
    
    existing = find_contact_by_phone(phone)
    if not existing:
        print(f"❌ Contact not found for {phone}")
        sys.exit(1)
    
    print(f"📱 Found: {existing}")
    
    if args.first_name:
        r = update_first_name(phone, args.first_name)
        print(f"  First name: {r}")
    
    if args.last_name:
        r = update_last_name(phone, args.last_name)
        print(f"  Last name: {r}")
    
    if args.alt_phone:
        r = add_alt_phone(phone, args.alt_phone)
        print(f"  Alt phone: {r}")
    
    if args.company:
        r = add_company(phone, args.company)
        print(f"  Company: {r}")
    
    if args.note:
        r = update_note(phone, args.note)
        print(f"  Note: {r}")
    
    if not any([args.first_name, args.last_name, args.alt_phone, args.company, args.note]):
        print("  (no updates specified)")


if __name__ == '__main__':
    main()
